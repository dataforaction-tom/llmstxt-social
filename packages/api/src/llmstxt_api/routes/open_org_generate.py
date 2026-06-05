"""POST /api/open-org/generate — kick off Open Org profile generation.

Unauthenticated by design (per spec section 1): any visitor can submit a
charity number. The Celery task runs the generator, populates the row, and
emails a magic-link claim to ``owner_email`` — that's where ownership gets
established.

A conflict is returned for an existing ``ready`` profile to prevent overwriting
a published profile someone else already owns. ``failed`` rows are retryable
(the most common cause is a transient CC API hiccup).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import re as _re

from llmstxt_api.config import settings
from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgProfile
from llmstxt_api.services.llm_usage import is_within_daily_budget
from llmstxt_api.tasks.open_org_generate import generate_open_org_profile_task
from llmstxt_core.enrichers.charity_commission import fetch_charity_data


router = APIRouter(prefix="/api/open-org", tags=["open-org"])


# Loose email check — Resend handles real deliverability. Pulling in
# ``pydantic[email]`` (which needs ``email-validator``) for a single use
# isn't worth the dep.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class GenerateRequest(BaseModel):
    charity_number: str = Field(
        ...,
        pattern=r"^[0-9]{6,8}$",
        description="UK Charity Commission registration number (6-8 digits).",
    )
    owner_email: str = Field(
        ...,
        pattern=_EMAIL_PATTERN,
        description="Email to send the claim/magic-link to when generation completes.",
    )


class GenerateResponse(BaseModel):
    org_id: str
    profile_id: str
    generation_status: str
    task_id: str | None = None


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_profile(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    org_id = f"GB-CHC-{request.charity_number}"

    # Locked decision #10: £0.50/org/day soft cap. Each generation runs two
    # LLM calls (mission rewrite + theme extract) — cheap, but the per-IP
    # rate limit alone isn't enough to deter someone re-running the same
    # charity in a tight loop. Note this is keyed on org_id, not IP, so
    # rotating IPs doesn't bypass it.
    if not await is_within_daily_budget(db, org_id=org_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "daily_budget_exceeded",
                "org_id": org_id,
                "message": "This organisation has reached today's £0.50 spend cap.",
            },
        )

    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    existing = result.scalar_one_or_none()

    if existing is not None and existing.generation_status != "failed":
        # A pending/generating/ready profile is owned (or about to be) by the
        # current claimant flow; refuse to overwrite. The owner can edit via
        # the admin routes after claiming.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "profile_already_exists",
                "org_id": org_id,
                "generation_status": existing.generation_status,
            },
        )

    if existing is None:
        profile = OrgProfile(org_id=org_id, generation_status="pending")
        db.add(profile)
    else:
        # Retry after a failed run — clear the error and re-queue.
        profile = existing
        profile.generation_status = "pending"
        profile.generation_error = None

    await db.commit()
    await db.refresh(profile)

    handle = generate_open_org_profile_task.delay(
        profile_id=str(profile.id),
        charity_number=request.charity_number,
        owner_email=request.owner_email,
    )

    return GenerateResponse(
        org_id=org_id,
        profile_id=str(profile.id),
        generation_status="pending",
        task_id=getattr(handle, "id", None),
    )


class GenerateStatusResponse(BaseModel):
    org_id: str
    status: str
    stage: str | None
    message: str | None
    payload: dict | None
    elapsed_ms: int


@router.get(
    "/generate/{org_id}/status",
    response_model=GenerateStatusResponse,
)
async def generate_status(
    org_id: str,
    db: AsyncSession = Depends(get_db),
) -> GenerateStatusResponse:
    """Live polling endpoint for the Generate.tsx live progress display.

    Unauthenticated — see spec section 1. The page polls every 2s during
    the 30-90s generation window.
    """
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")

    started = row.generation_started_at
    finished = row.generation_finished_at
    from datetime import datetime as _dt

    if finished is not None and started is not None:
        elapsed = int((finished - started).total_seconds() * 1000)
    elif started is not None:
        elapsed = int((_dt.utcnow() - started).total_seconds() * 1000)
    else:
        elapsed = 0

    return GenerateStatusResponse(
        org_id=row.org_id,
        status=row.generation_status,
        stage=row.generation_stage,
        message=row.generation_message,
        payload=row.generation_payload,
        elapsed_ms=elapsed,
    )


_NUMBER_RE = _re.compile(r"^[0-9]{6,8}$")


class LookupResponse(BaseModel):
    number: str
    name: str
    registered_address: str | None


def _format_address(contact: dict | None) -> str | None:
    if not contact:
        return None
    addr = contact.get("address") or {}
    parts = [addr.get(k) for k in ("line1", "line2", "line3", "city", "postcode")]
    cleaned = [p for p in parts if p]
    return ", ".join(cleaned) if cleaned else None


@router.get(
    "/lookup/{number}",
    response_model=LookupResponse,
)
async def lookup_charity(number: str) -> LookupResponse:
    """Look up a UK charity by registration number.

    Powers the inline "Match: <name>" reassurance line on the Generate page.
    Cached weakly upstream by the CC enricher; this endpoint adds no extra
    caching beyond what the enricher already provides.
    """
    if not _NUMBER_RE.match(number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="number must be 6-8 digits",
        )
    cd = await fetch_charity_data(number, api_key=settings.charity_commission_api_key)
    if cd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="charity not found",
        )
    return LookupResponse(
        number=cd.number,
        name=cd.name,
        registered_address=_format_address(cd.contact),
    )


__all__ = [
    "GenerateRequest",
    "GenerateResponse",
    "GenerateStatusResponse",
    "LookupResponse",
    "generate_profile",
    "generate_status",
    "lookup_charity",
    "router",
]
