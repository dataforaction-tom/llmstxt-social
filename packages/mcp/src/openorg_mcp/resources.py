"""Resource implementations for the Open Org MCP server.

Resources are addressable by URI templates and return the same data as the
tools, but in a resource-oriented style for MCP clients that prefer URI-based
access (e.g. Claude Desktop's resource browser).

Registered URI templates (in ``server.py``):
  * ``openorg://orgs/{org_id}/profile``           — full profile JSON
  * ``openorg://orgs/{org_id}/ideas/{slug}``       — individual idea
  * ``openorg://orgs/{org_id}/strategies/{slug}``  — individual strategy
  * ``openorg://themes``                           — controlled vocabulary
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.open_org_models import OrgIdea, OrgProfile, OrgStrategy
from llmstxt_core.open_org.themes import load_themes


async def read_profile_resource(
    db: AsyncSession, *, org_id: str
) -> dict[str, Any] | None:
    """Return the full profile JSON for a published org (or None)."""
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalars().one_or_none()
    if profile is None or profile.profile_json is None:
        return None
    return profile.profile_json


async def read_idea_resource(
    db: AsyncSession, *, org_id: str, slug: str
) -> dict[str, Any] | None:
    """Return a single published idea by (org_id, slug)."""
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id,
            OrgIdea.slug == slug,
            OrgIdea.published.is_(True),
        )
    )
    idea = result.scalars().one_or_none()
    if idea is None:
        return None
    payload = dict(idea.idea_json or {})
    payload["slug"] = idea.slug
    payload["org_id"] = idea.org_id
    return payload


async def read_strategy_resource(
    db: AsyncSession, *, org_id: str, slug: str
) -> dict[str, Any] | None:
    """Return a single published strategy by (org_id, slug)."""
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id,
            OrgStrategy.slug == slug,
            OrgStrategy.published.is_(True),
        )
    )
    strategy = result.scalars().one_or_none()
    if strategy is None:
        return None
    payload = dict(strategy.strategy_json or {})
    payload["slug"] = strategy.slug
    payload["org_id"] = strategy.org_id
    return payload


async def read_themes_resource() -> list[dict[str, Any]]:
    """Return the controlled theme vocabulary (no DB required)."""
    return load_themes()


__all__ = [
    "read_profile_resource",
    "read_idea_resource",
    "read_strategy_resource",
    "read_themes_resource",
]