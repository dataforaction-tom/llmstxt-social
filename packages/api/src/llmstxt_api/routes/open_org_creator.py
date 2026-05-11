"""Strategy / idea chat creator routes.

Drives a guided conversation that produces validated Open Org markdown ready
to drop into the editor. Each session is one strategy or one idea. Messages
stream back via SSE; the live preview is updated by the model calling
``update_current_markdown``.

Auth: gated by :func:`require_org_admin`. The session's ``org_id`` is checked
on every request so an admin of org A can't poke at a session belonging to
org B even with a valid session ID.

Cost cap: locked decision #10 says £0.50/org/day. Both creation and per-
message endpoints gate on ``is_within_daily_budget`` and return 429 above it.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import AsyncIterator, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.config import settings
from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import (
    CreatorSession,
    OrgAdmin,
    OrgIdea,
    OrgProfile,
    OrgStrategy,
)
from llmstxt_api.routes.open_org_auth import require_org_admin
from llmstxt_api.services.llm_usage import is_within_daily_budget, log_usage
from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.converter import ConverterError, markdown_to_json
from llmstxt_core.open_org.creator.conversation import start_turn
from llmstxt_core.open_org.creator.extractors import (
    ExtractError,
    UnsupportedFormatError,
    extract_text,
)


log = logging.getLogger(__name__)


router = APIRouter(prefix="/api/open-org", tags=["open-org-creator"])


# Sessions expire after 30 days of inactivity per spec section 2.
_SESSION_TTL_DAYS = 30


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


CreatorKind = Literal["strategy", "idea"]


class CreateSessionResponse(BaseModel):
    session_id: uuid.UUID
    kind: CreatorKind
    org_id: str
    current_markdown: str | None = None


class SessionDetail(BaseModel):
    session_id: uuid.UUID
    kind: CreatorKind
    org_id: str
    conversation_history: list[dict] = Field(default_factory=list)
    current_markdown: str | None = None
    expires_at: datetime


class MessagePayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=20_000)


class FinalizeResponse(BaseModel):
    kind: CreatorKind
    org_id: str
    slug: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_session(
    db: AsyncSession, session_id: uuid.UUID, admin: OrgAdmin
) -> CreatorSession:
    result = await db.execute(
        select(CreatorSession).where(CreatorSession.id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    if row.org_id != admin.org_id:
        # Don't reveal that the session exists for a different org.
        raise HTTPException(status_code=403, detail="not an admin of this session")
    return row


async def _enforce_budget(db: AsyncSession, org_id: str) -> None:
    if not await is_within_daily_budget(db, org_id=org_id):
        raise HTTPException(
            status_code=429,
            detail={"error": "daily_budget_exceeded", "org_id": org_id},
        )


def _build_org_profile_summary(profile: OrgProfile | None) -> str | None:
    if profile is None or not profile.profile_json:
        return None
    identity = profile.profile_json.get("identity", {}) or {}
    mission = profile.profile_json.get("mission", {}) or {}
    name = identity.get("name") or ""
    themes = ", ".join(mission.get("themes") or [])
    summary = mission.get("summary") or ""
    parts: list[str] = []
    if name:
        parts.append(f"Name: {name}")
    if themes:
        parts.append(f"Themes: {themes}")
    if summary:
        parts.append(f"Mission: {summary}")
    return "\n".join(parts) if parts else None


async def _load_profile(db: AsyncSession, org_id: str) -> OrgProfile | None:
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Create session
# ---------------------------------------------------------------------------


@router.post("/{org_id}/create/{kind}", response_model=CreateSessionResponse)
async def create_session(
    org_id: str,
    kind: str,
    upload: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
) -> CreateSessionResponse:
    if kind not in ("strategy", "idea"):
        raise HTTPException(
            status_code=400, detail=f"unknown kind: {kind!r}"
        )

    await _enforce_budget(db, admin.org_id)

    seed_history: list[dict] = []
    if upload is not None:
        try:
            content = await upload.read()
            text = extract_text(upload.filename or "upload", content)
        except UnsupportedFormatError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        except ExtractError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        seed_history.append(
            {
                "role": "user",
                "content": (
                    "Here's an existing document I'd like to work from. Use it "
                    "as context, then start the conversation:\n\n"
                    + text
                ),
            }
        )

    session_row = CreatorSession(
        # Pre-assign the UUID so the response can be returned without a
        # post-commit refresh (one fewer round-trip; matches the rest of the
        # routes in this codebase that lean on model-side defaults).
        id=uuid.uuid4(),
        org_id=admin.org_id,
        kind=kind,
        conversation_history=seed_history,
        current_markdown=None,
        expires_at=datetime.utcnow() + timedelta(days=_SESSION_TTL_DAYS),
    )
    db.add(session_row)
    await db.commit()

    return CreateSessionResponse(
        session_id=session_row.id,
        kind=kind,
        org_id=admin.org_id,
        current_markdown=None,
    )


# ---------------------------------------------------------------------------
# Get session
# ---------------------------------------------------------------------------


@router.get("/create/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
) -> SessionDetail:
    session_row = await _load_session(db, session_id, admin)
    return SessionDetail(
        session_id=session_row.id,
        kind=session_row.kind,
        org_id=session_row.org_id,
        conversation_history=session_row.conversation_history or [],
        current_markdown=session_row.current_markdown,
        expires_at=session_row.expires_at,
    )


# ---------------------------------------------------------------------------
# Post message — streams SSE
# ---------------------------------------------------------------------------


@router.post("/create/{session_id}/message")
async def post_message(
    session_id: uuid.UUID,
    payload: MessagePayload,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    session_row = await _load_session(db, session_id, admin)

    if session_row.expires_at and session_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="session expired")

    await _enforce_budget(db, admin.org_id)

    profile = await _load_profile(db, admin.org_id)
    org_summary = _build_org_profile_summary(profile)

    history = list(session_row.conversation_history or [])
    user_message = payload.content
    history_for_prompt = list(history)

    client = CachedAnthropic(api_key=settings.anthropic_api_key)

    async def event_stream() -> AsyncIterator[bytes]:
        nonlocal history
        assistant_text_parts: list[str] = []
        final_markdown: str | None = None
        usage = None

        with start_turn(
            client=client,
            kind=session_row.kind,
            conversation_history=history_for_prompt,
            user_message=user_message,
            org_profile_summary=org_summary,
        ) as turn:
            for chunk in turn.text_stream:
                if not chunk:
                    continue
                assistant_text_parts.append(chunk)
                yield _sse_event("delta", {"text": chunk})
            final_markdown = turn.final_markdown()
            usage = turn.usage()

        assistant_text = "".join(assistant_text_parts)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_text})

        session_row.conversation_history = history
        session_row.last_active_at = datetime.utcnow()
        if final_markdown:
            session_row.current_markdown = final_markdown

        if usage is not None:
            log_usage(
                db, feature=f"{session_row.kind}_creator", usage=usage, org_id=admin.org_id
            )
        await db.commit()

        yield _sse_event(
            "done",
            {
                "current_markdown": session_row.current_markdown,
                "usage": {
                    "input_tokens": usage.input_tokens if usage else 0,
                    "output_tokens": usage.output_tokens if usage else 0,
                },
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse_event(event: str, data: dict) -> bytes:
    """Format a Server-Sent Events frame."""
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Finalize — create OrgStrategy / OrgIdea row from the session
# ---------------------------------------------------------------------------


@router.post("/create/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
) -> FinalizeResponse:
    session_row = await _load_session(db, session_id, admin)
    if not session_row.current_markdown:
        raise HTTPException(
            status_code=400,
            detail="session has no markdown yet; send messages first",
        )

    try:
        derived = markdown_to_json(
            session_row.current_markdown, kind=session_row.kind
        )
    except ConverterError as exc:
        raise HTTPException(
            status_code=400, detail={"errors": exc.errors}
        ) from exc

    slug = derived.get("id")
    if not isinstance(slug, str) or not slug:
        raise HTTPException(
            status_code=400,
            detail="markdown frontmatter must include a non-empty 'id' for the slug",
        )

    if session_row.kind == "strategy":
        row = OrgStrategy(
            org_id=admin.org_id,
            slug=slug,
            markdown_source=session_row.current_markdown,
            strategy_json=derived,
            status=derived.get("status", "draft"),
            themes=derived.get("themes"),
        )
    else:
        row = OrgIdea(
            org_id=admin.org_id,
            slug=slug,
            markdown_source=session_row.current_markdown,
            idea_json=derived,
            status=derived.get("status", "seed"),
            themes=derived.get("themes"),
        )
    db.add(row)
    await db.commit()

    return FinalizeResponse(
        kind=session_row.kind,
        org_id=admin.org_id,
        slug=slug,
    )


__all__ = [
    "CreateSessionResponse",
    "FinalizeResponse",
    "MessagePayload",
    "SessionDetail",
    "create_session",
    "finalize_session",
    "get_session",
    "post_message",
    "router",
]
