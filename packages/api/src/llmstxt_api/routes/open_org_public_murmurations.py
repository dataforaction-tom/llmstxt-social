"""Public Murmurations envelope routes.

GET /open-org/{org_id}/murmurations.json returns the flat shape the
Murmurations index fetches and validates against ``open_org_profile-v0.1.0``.
This is the URL we POST to the index — it's a stable public address with a
5-minute cache (the index expects a fetchable URL, not a body payload).

GET /open-org/{org_id}/strategies/{slug}/murmurations.json returns the
per-record strategy envelope (``open_org_strategy-v0.1.0``).

GET /open-org/{org_id}/ideas/{slug}/murmurations.json returns the
per-record idea envelope (``open_org_idea-v0.1.0``).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.config import settings
from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgIdea, OrgProfile, OrgStrategy
from llmstxt_core.enrichers.postcodes_io import lookup_geolocation
from llmstxt_core.open_org.murmurations import build_envelope
from llmstxt_core.open_org.murmurations_per_record import (
    build_strategy_envelope,
    build_idea_envelope,
)
from llmstxt_core.open_org.ons_geography import lookup_lad_centroid


router = APIRouter(prefix="/open-org", tags=["open-org-public"])

_CACHE_CONTROL = "public, max-age=300"


@router.get("/{org_id}/murmurations.json")
async def get_murmurations_envelope(
    org_id: str, db: AsyncSession = Depends(get_db)
):
    profile_result = await db.execute(
        select(OrgProfile).where(OrgProfile.org_id == org_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None or not profile.published or not profile.profile_json:
        # 404 (not 403/500) so the index treats it as a dead profile and the
        # public can't tell a missing org from an unpublished draft.
        raise HTTPException(status_code=404, detail="profile not found")

    strategy_themes = await _collect_strategy_themes(db, org_id)
    ideas_count = await _count_published_ideas(db, org_id)

    envelope = await build_envelope(
        profile.profile_json,
        frontend_base_url=settings.frontend_url,
        postcodes_io_lookup=lookup_geolocation,
        ons_centroid_lookup=lookup_lad_centroid,
        strategy_themes=strategy_themes,
        ideas_count=ideas_count,
    )

    return Response(
        content=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/strategies/{slug}/murmurations.json")
async def get_strategy_murmurations_envelope(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    """Per-record Murmurations envelope for a published strategy."""
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id,
            OrgStrategy.slug == slug,
            OrgStrategy.published.is_(True),
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None or not strategy.strategy_json:
        raise HTTPException(status_code=404, detail="strategy not found")

    envelope = build_strategy_envelope(
        strategy.strategy_json,
        org_id=org_id,
        frontend_base_url=settings.frontend_url,
    )

    return Response(
        content=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/ideas/{slug}/murmurations.json")
async def get_idea_murmurations_envelope(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    """Per-record Murmurations envelope for a published idea."""
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id,
            OrgIdea.slug == slug,
            OrgIdea.published.is_(True),
        )
    )
    idea = result.scalar_one_or_none()
    if idea is None or not idea.idea_json:
        raise HTTPException(status_code=404, detail="idea not found")

    envelope = build_idea_envelope(
        idea.idea_json,
        org_id=org_id,
        frontend_base_url=settings.frontend_url,
    )

    return Response(
        content=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


async def _collect_strategy_themes(db: AsyncSession, org_id: str) -> list[str]:
    """Return the de-duplicated theme list across all published strategies."""
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id, OrgStrategy.published.is_(True)
        )
    )
    strategies = result.scalars().all()
    seen: list[str] = []
    seen_set: set[str] = set()
    for strategy in strategies:
        for theme in strategy.themes or []:
            if isinstance(theme, str) and theme not in seen_set:
                seen.append(theme)
                seen_set.add(theme)
    return seen


async def _count_published_ideas(db: AsyncSession, org_id: str) -> int:
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id, OrgIdea.published.is_(True)
        )
    )
    return len(result.scalars().all())


__all__ = ["router", "get_murmurations_envelope"]
