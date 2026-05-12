"""Public Open Org JSON serving routes (no auth).

These URLs are the canonical public profile addresses indexed by Murmurations
and fetched by discovery clients. Unpublished records return 404 to avoid
leaking existence — there's no signed-in identity to gate on.

Mount at the FastAPI app root (not under ``/api``) so URLs are clean::

    /open-org/{org_id}/profile.json
    /open-org/{org_id}/strategies/{slug}.json
    /open-org/{org_id}/ideas/{slug}.json
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgIdea, OrgProfile, OrgStrategy


router = APIRouter(prefix="/open-org", tags=["open-org-public"])

# 5-minute browser/CDN cache. Cloudflare edge can layer a longer one if wanted.
_CACHE_CONTROL = "public, max-age=300"


@router.get("/{org_id}/profile.json")
async def get_profile_json(org_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OrgProfile).where(OrgProfile.org_id == org_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None or not profile.published:
        raise HTTPException(status_code=404, detail="profile not found")
    return Response(
        content=_json_response_body(profile.profile_json),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/strategies/{slug}.json")
async def get_strategy_json(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id,
            OrgStrategy.slug == slug,
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None or not strategy.published:
        raise HTTPException(status_code=404, detail="strategy not found")
    return Response(
        content=_json_response_body(strategy.strategy_json),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/ideas/{slug}.json")
async def get_idea_json(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id,
            OrgIdea.slug == slug,
        )
    )
    idea = result.scalar_one_or_none()
    if idea is None or not idea.published:
        raise HTTPException(status_code=404, detail="idea not found")
    return Response(
        content=_json_response_body(idea.idea_json),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/strategies")
async def list_strategies(org_id: str, db: AsyncSession = Depends(get_db)):
    """List published strategies for an org as a JSON array of summaries.

    Each entry: ``{slug, themes, status, summary?}``. ``summary`` is the
    first ~280 chars of the strategy's body summary (markdown ``## Summary``
    section) when present.

    404s if the parent profile isn't published — keeps the existence-leak
    rules consistent with the per-record routes.
    """
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgStrategy)
        .where(OrgStrategy.org_id == org_id, OrgStrategy.published.is_(True))
        .order_by(OrgStrategy.created_at.desc())
    )
    rows = result.scalars().all()
    summaries = [_record_summary(r.slug, r.themes, r.status, r.strategy_json) for r in rows]
    return Response(
        content=_json_list_body(summaries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/ideas")
async def list_ideas(org_id: str, db: AsyncSession = Depends(get_db)):
    """List published ideas for an org as a JSON array of summaries.

    Each entry: ``{slug, themes, status, summary?}``. Same envelope shape
    as the strategies list.
    """
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgIdea)
        .where(OrgIdea.org_id == org_id, OrgIdea.published.is_(True))
        .order_by(OrgIdea.created_at.desc())
    )
    rows = result.scalars().all()
    summaries = [_record_summary(r.slug, r.themes, r.status, r.idea_json) for r in rows]
    return Response(
        content=_json_list_body(summaries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


async def _profile_is_published(db: AsyncSession, org_id: str) -> bool:
    result = await db.execute(
        select(OrgProfile.published).where(OrgProfile.org_id == org_id)
    )
    row = result.scalar_one_or_none()
    return bool(row)


def _record_summary(
    slug: str,
    themes: list[str] | None,
    status: str | None,
    record_json: dict | None,
) -> dict:
    summary_text = ""
    if isinstance(record_json, dict):
        candidate = record_json.get("summary")
        if isinstance(candidate, str):
            summary_text = candidate.strip()[:280]
    entry: dict = {
        "slug": slug,
        "themes": list(themes or []),
    }
    if status:
        entry["status"] = status
    if summary_text:
        entry["summary"] = summary_text
    return entry


def _json_response_body(payload: dict | None) -> bytes:
    """Serialize a JSONB column to bytes. Empty payload renders as ``{}``."""
    import json
    return json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")


def _json_list_body(items: list[dict]) -> bytes:
    import json
    return json.dumps(items, ensure_ascii=False).encode("utf-8")
