"""Celery task that runs the Open Org profile generator and emails a claim link.

Splits into two layers:

* :func:`_run_generation` — the async work. All side-effecting collaborators
  are injectable so tests run without Celery, without a DB, and without
  Resend.
* :func:`generate_open_org_profile_task` — the Celery entry point. Wires the
  collaborators to their production implementations and runs the coroutine.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from llmstxt_api.config import settings
from llmstxt_api.open_org_models import OrgProfile
from llmstxt_api.routes.open_org_auth import create_claim_token
from llmstxt_api.services import llm_usage as llm_usage_service
from llmstxt_api.tasks.celery import celery_app
from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.generator import (
    GenerationResult,
    generate_profile_from_charity_number,
)


log = logging.getLogger(__name__)

# Truncate failed-generation error messages so the column can't be jammed with
# a 1MB SDK stack trace if something goes very wrong.
_ERROR_MESSAGE_MAX = 1000


GeneratorFn = Callable[..., Awaitable[GenerationResult]]
SendEmailFn = Callable[..., Awaitable[None]]


# ---------------------------------------------------------------------------
# Production collaborators
# ---------------------------------------------------------------------------


def _build_session_maker():
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _default_generator(
    *,
    charity_number: str,
    anthropic_client: CachedAnthropic,
    cc_api_key: str | None,
) -> GenerationResult:
    return await generate_profile_from_charity_number(
        charity_number,
        anthropic_client=anthropic_client,
        cc_api_key=cc_api_key,
    )


async def _default_send_claim_email(
    *,
    db: AsyncSession,
    email: str,
    org_id: str,
) -> None:
    raw_token, _row = await create_claim_token(db, email=email, org_id=org_id)
    await db.commit()

    claim_url = f"{settings.frontend_url}/auth/verify?token={raw_token}"

    # Dev mode: skip Resend and log the claim URL so the developer can
    # copy-paste from ``docker compose`` output without Resend deliverability
    # configured.
    if settings.environment == "development":
        print(
            "\n"
            "==================================================\n"
            f"CLAIM LINK for {email} ({org_id}):\n"
            f"{claim_url}\n"
            "==================================================\n",
            flush=True,
        )
        return

    try:
        resend.Emails.send(
            {
                "from": settings.from_email,
                "to": [email],
                "subject": "Your Open Org profile is ready to claim",
                "html": _claim_email_html(claim_url, org_id),
            }
        )
    except Exception as exc:  # noqa: BLE001
        # Don't mark the generation as failed just because the email bounced —
        # the row is already ready, and the operator can resend manually.
        log.warning("claim email send failed for %s (%s): %s", email, org_id, exc)


def _claim_email_html(claim_url: str, org_id: str) -> str:
    return (
        '<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">'
        '<h2 style="color: #6366f1;">Your Open Org profile is ready</h2>'
        f"<p>We've generated an Open Org profile for <strong>{org_id}</strong>.</p>"
        "<p>Click below to claim ownership and review the profile before publishing. "
        "This link expires in 24 hours.</p>"
        f'<a href="{claim_url}" style="display: inline-block; background: #6366f1; '
        "color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; "
        'margin: 16px 0;">Claim your profile</a>'
        '<p style="color: #666; font-size: 12px; margin-top: 32px;">'
        f"Or copy this link: {claim_url}</p>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Core async function (testable in isolation)
# ---------------------------------------------------------------------------


async def _run_generation(
    *,
    profile_id: uuid.UUID,
    charity_number: str,
    owner_email: str,
    session_maker: Any,
    generator: GeneratorFn,
    send_claim_email: SendEmailFn,
    anthropic_client: CachedAnthropic | None = None,
    cc_api_key: str | None = None,
) -> None:
    """Run the generator and persist the result.

    Always returns; swallows generator exceptions into a ``failed`` row so the
    Celery worker doesn't retry blindly on user-facing data problems.
    """
    from datetime import datetime as _dt

    async with session_maker() as session:
        row = await _fetch_row(session, profile_id)
        if row is None:
            log.error("OrgProfile row %s not found for generation", profile_id)
            return

        row.generation_status = "generating"
        row.generation_error = None
        row.generation_stage = "extracting"
        row.generation_message = "Reading what we found…"
        row.generation_started_at = _dt.utcnow()
        row.generation_finished_at = None
        row.generation_payload = None
        await session.commit()

        try:
            result = await generator(
                charity_number=charity_number,
                anthropic_client=anthropic_client,
                cc_api_key=cc_api_key,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)[:_ERROR_MESSAGE_MAX] or exc.__class__.__name__
            row.generation_status = "failed"
            row.generation_error = message
            row.generation_stage = "error"
            row.generation_message = "Couldn't finish — see error below."
            row.generation_finished_at = _dt.utcnow()
            await session.commit()
            log.warning(
                "open_org generation failed for %s: %s", charity_number, message
            )
            return

        row.markdown_source = result.markdown
        row.profile_json = result.json_payload
        row.generation_status = "ready"
        row.generation_error = None
        row.generation_stage = "done"
        row.generation_message = "Draft ready."
        row.generation_finished_at = _dt.utcnow()
        row.generation_payload = _summary_payload(result.json_payload)

        llm_usage_service.log_usage(
            session,
            feature="profile_generator",
            usage=result.total_usage,
            org_id=result.org_id,
        )
        await session.commit()

        await send_claim_email(
            db=session, email=owner_email, org_id=result.org_id
        )


def _summary_payload(profile_json: dict | None) -> dict:
    """Compact preview of what the generator found.

    Drives the "14 programmes mentioned, 4 themes…" line on the Generate page's
    success state. Pure derivation from the JSON.
    """
    if not profile_json:
        return {}
    mission = profile_json.get("mission") or {}
    return {
        "themes_count": len(mission.get("themes") or []),
        "programmes_count": len(mission.get("programmes") or []),
        "has_summary": bool((mission.get("summary") or "").strip()),
    }


async def _fetch_row(session: AsyncSession, profile_id: uuid.UUID) -> OrgProfile | None:
    result = await session.execute(
        select(OrgProfile).where(OrgProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------


@celery_app.task(name="open_org_generate_profile", bind=True)
def generate_open_org_profile_task(
    self,
    *,
    profile_id: str,
    charity_number: str,
    owner_email: str,
):
    """Celery task wrapper.

    Builds production collaborators and runs the async core function. Keyword
    arguments keep dispatch sites self-documenting.
    """
    profile_uuid = uuid.UUID(profile_id)
    session_maker = _build_session_maker()

    anthropic_client = CachedAnthropic(api_key=settings.anthropic_api_key)
    cc_api_key = settings.charity_commission_api_key

    asyncio.run(
        _run_generation(
            profile_id=profile_uuid,
            charity_number=charity_number,
            owner_email=owner_email,
            session_maker=session_maker,
            generator=_default_generator,
            send_claim_email=_default_send_claim_email,
            anthropic_client=anthropic_client,
            cc_api_key=cc_api_key,
        )
    )


__all__ = [
    "_run_generation",
    "generate_open_org_profile_task",
]
