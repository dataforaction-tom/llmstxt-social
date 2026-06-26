"""Public funder signalling routes (Phase 1 — no auth).

Funders signal interest in a published idea. Organisations can see who is
looking at their work — a power shift from gatekeeping to discovery.

Mount under ``/api/open-org`` so the URLs are::

    POST /api/open-org/ideas/{org_id}/{slug}/signal
    GET  /api/open-org/ideas/{org_id}/{slug}/signals
    GET  /api/open-org/{org_id}/signals

All body fields are optional so a funder can signal anonymously. Phase 1 is
transparent: signals are publicly visible.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgIdea, OrgProfile, OrgSignal

router = APIRouter(prefix="/api/open-org", tags=["open-org-signals"])


class SignalBody(BaseModel):
    """Body for POST /signal. All fields optional — anonymous signalling is fine."""

    funder_name: str | None = None
    funder_email: str | None = None
    message: str | None = None


class SignalOut(BaseModel):
    id: str
    idea_id: str | None
    org_id: str
    signal_type: str
    funder_name: str | None
    funder_email: str | None
    message: str | None
    created_at: str


# --- helpers ---------------------------------------------------------------


async def _profile_is_published(db: AsyncSession, org_id: str) -> bool:
    result = await db.execute(
        select(OrgProfile.published).where(OrgProfile.org_id == org_id)
    )
    row = result.scalar_one_or_none()
    return bool(row)


async def _get_published_idea(
    db: AsyncSession, org_id: str, slug: str
) -> OrgIdea | None:
    """Return the published idea, or None if the profile/idea isn't published."""
    if not await _profile_is_published(db, org_id):
        return None
    result = await db.execute(
        select(OrgIdea).where(OrgIdea.org_id == org_id, OrgIdea.slug == slug)
    )
    idea = result.scalar_one_or_none()
    if idea is None or not idea.published:
        return None
    return idea


def _signal_to_out(s: OrgSignal) -> SignalOut:
    return SignalOut(
        id=str(s.id),
        idea_id=str(s.idea_id) if s.idea_id else None,
        org_id=s.org_id,
        signal_type=s.signal_type,
        funder_name=s.funder_name,
        funder_email=s.funder_email,
        message=s.message,
        created_at=s.created_at.isoformat() if isinstance(s.created_at, datetime) else str(s.created_at),
    )


# --- routes ----------------------------------------------------------------


@router.post("/ideas/{org_id}/{slug}/signal", response_model=SignalOut, status_code=201)
async def create_signal(
    org_id: str,
    slug: str,
    body: SignalBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a funder signal of interest on a published idea.

    404 if the profile or idea is not published — same existence-leak rules as
    the rest of the public API.
    """
    idea = await _get_published_idea(db, org_id, slug)
    if idea is None:
        raise HTTPException(status_code=404, detail="idea not found")

    payload = body or SignalBody()
    signal = OrgSignal(
        idea_id=idea.id,
        org_id=org_id,
        signal_type="interest",
        funder_name=payload.funder_name,
        funder_email=payload.funder_email,
        message=payload.message,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return _signal_to_out(signal)


@router.get("/ideas/{org_id}/{slug}/signals", response_model=list[SignalOut])
async def list_idea_signals(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    """List signals for a published idea, most recent first."""
    idea = await _get_published_idea(db, org_id, slug)
    if idea is None:
        raise HTTPException(status_code=404, detail="idea not found")
    result = await db.execute(
        select(OrgSignal)
        .where(OrgSignal.idea_id == idea.id)
        .order_by(OrgSignal.created_at.desc())
    )
    signals = result.scalars().all()
    return [_signal_to_out(s) for s in signals]


@router.get("/{org_id}/signals", response_model=list[SignalOut])
async def list_org_signals(org_id: str, db: AsyncSession = Depends(get_db)):
    """List all signals for an org across all ideas, most recent first."""
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgSignal)
        .where(OrgSignal.org_id == org_id)
        .order_by(OrgSignal.created_at.desc())
    )
    signals = result.scalars().all()
    return [_signal_to_out(s) for s in signals]