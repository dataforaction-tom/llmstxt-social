"""Public read-only tool implementations for the Open Org MCP server.

Each tool is a plain ``async`` function that accepts an ``AsyncSession`` (and
tool-specific keyword arguments). This design makes the tools trivially
testable with ``unittest.mock.AsyncMock`` — no real Postgres connection is
required.

The tools are registered on a ``FastMCP`` server instance in ``server.py``.
All tools are read-only and require no authentication; admin/auth tools are
Step 8.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.open_org_models import (
    ExternalOrgCache,
    OrgIdea,
    OrgProfile,
    OrgStrategy,
)
from llmstxt_core.open_org.themes import load_themes

# Reuse the API's graph builder so the MCP server stays in lock-step with the
# discovery route's visualisation logic without duplicating ~230 lines of code.
from llmstxt_api.routes.open_org_discovery import (
    _build_graph,
    _external_to_row,
    _local_to_row,
    _matches_filters,
)


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


async def get_profile(db: AsyncSession, *, org_id: str) -> dict | None:
    """Fetch an org's full profile JSON by ``org_id``.

    Returns ``None`` for unpublished or missing orgs — no existence leak.
    """
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalars().one_or_none()
    # Defensive Python-side check: mocked sessions ignore SQL WHERE clauses,
    # and even with a real DB a race between query and read is possible.
    if profile is None or not profile.published or profile.profile_json is None:
        return None
    return profile.profile_json


# ---------------------------------------------------------------------------
# search_profiles
# ---------------------------------------------------------------------------


async def search_profiles(
    db: AsyncSession,
    *,
    theme: str | None = None,
    place: str | None = None,
    q: str | None = None,
    area_code: str | None = None,
) -> list[dict[str, Any]]:
    """Search published org profiles by theme, place, or name.

    Mirrors the API discovery route's query logic: a union of local published
    ``OrgProfile`` rows and federated ``ExternalOrgCache`` rows, filtered by
    theme / area_code / free-text query. Local profiles win over federated
    rows for the same ``org_id``.
    """
    local_query = select(OrgProfile).where(OrgProfile.published.is_(True))
    external_query = select(ExternalOrgCache)

    # Coarse JSONB filters — same approach as the API route. The Python-side
    # ``_matches_filters`` re-checks everything (JSONB containment only narrows
    # the candidate set).
    if theme:
        local_query = local_query.where(
            OrgProfile.profile_json["mission"]["themes"].op("?")(theme)
        )
        external_query = external_query.where(
            ExternalOrgCache.profile_json["tags"].op("?")(theme)
        )

    if q:
        like = f"%{q.lower()}%"
        local_query = local_query.where(
            or_(
                OrgProfile.profile_json["identity"]["name"]
                .as_string()
                .ilike(like),
                OrgProfile.org_id.ilike(like),
            )
        )
        external_query = external_query.where(
            or_(
                ExternalOrgCache.profile_json["name"].as_string().ilike(like),
                ExternalOrgCache.org_id.ilike(like),
            )
        )

    local_rows = (await db.execute(local_query)).scalars().all()
    external_rows = (await db.execute(external_query)).scalars().all()

    discovery_rows: list[dict[str, Any]] = []
    seen_org_ids: set[str] = set()

    for profile in local_rows:
        row = _local_to_row(profile)
        if row is None:
            continue
        if _matches_filters(row, theme=theme, area_code=area_code, q=q):
            discovery_rows.append(row.model_dump())
            seen_org_ids.add(row.org_id)

    for cached in external_rows:
        row = _external_to_row(cached)
        if row is None:
            continue
        # Local profile wins when both sides have the same org_id.
        if row.org_id in seen_org_ids:
            continue
        if _matches_filters(row, theme=theme, area_code=area_code, q=q):
            discovery_rows.append(row.model_dump())

    return discovery_rows


# ---------------------------------------------------------------------------
# get_ideas
# ---------------------------------------------------------------------------


async def get_ideas(
    db: AsyncSession, *, org_id: str
) -> list[dict[str, Any]]:
    """List published ideas for an org.

    Returns each idea's ``idea_json`` augmented with ``slug`` and ``org_id``
    for downstream consumption by AI agents.
    """
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id,
            OrgIdea.published.is_(True),
        )
    )
    ideas = result.scalars().all()
    out: list[dict[str, Any]] = []
    for idea in ideas:
        # Defensive Python-side filter — mocked sessions ignore SQL WHERE.
        if not idea.published:
            continue
        payload = dict(idea.idea_json or {})
        payload["slug"] = idea.slug
        payload["org_id"] = idea.org_id
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# get_strategies
# ---------------------------------------------------------------------------


async def get_strategies(
    db: AsyncSession, *, org_id: str
) -> list[dict[str, Any]]:
    """List published strategies for an org."""
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id,
            OrgStrategy.published.is_(True),
        )
    )
    strategies = result.scalars().all()
    out: list[dict[str, Any]] = []
    for strategy in strategies:
        # Defensive Python-side filter — mocked sessions ignore SQL WHERE.
        if not strategy.published:
            continue
        payload = dict(strategy.strategy_json or {})
        payload["slug"] = strategy.slug
        payload["org_id"] = strategy.org_id
        out.append(payload)
    return out


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


async def get_evidence(
    db: AsyncSession, *, org_id: str
) -> list[dict[str, Any]]:
    """List evidence items from a profile's ``evidence[]`` array.

    Returns an empty list if the org is unpublished, missing, or has no
    evidence key in its profile JSON.
    """
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalars().one_or_none()
    if profile is None or profile.profile_json is None:
        return []
    evidence = profile.profile_json.get("evidence")
    if not isinstance(evidence, list):
        return []
    return evidence


# ---------------------------------------------------------------------------
# get_themes
# ---------------------------------------------------------------------------


async def get_themes() -> list[dict[str, Any]]:
    """Return the Open Org controlled theme vocabulary.

    Reads from ``llmstxt_core.open_org.themes.load_themes()`` — the same
    vocabulary the API's ``GET /api/open-org/themes`` endpoint serves. No
    database connection required.
    """
    return load_themes()


# ---------------------------------------------------------------------------
# get_graph
# ---------------------------------------------------------------------------


async def get_graph(
    db: AsyncSession,
    *,
    themes: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return discovery graph data: nodes (orgs, ideas, strategies) and edges.

    Reuses the API route's ``_build_graph`` logic to stay in sync with the
    discovery visualisation. ``themes`` is a comma-separated string of theme
    keys; only nodes matching at least one are included.
    """
    theme_filter: set[str] | None = None
    if themes:
        if isinstance(themes, str):
            theme_list = [t.strip() for t in themes.split(",") if t.strip()]
        else:
            theme_list = [str(t).strip() for t in themes if str(t).strip()]
        theme_filter = set(theme_list) if theme_list else None

    profiles = (
        await db.execute(select(OrgProfile).where(OrgProfile.published.is_(True)))
    ).scalars().all()
    ideas = (
        await db.execute(select(OrgIdea).where(OrgIdea.published.is_(True)))
    ).scalars().all()
    strategies = (
        await db.execute(select(OrgStrategy).where(OrgStrategy.published.is_(True)))
    ).scalars().all()

    payload = _build_graph(
        profiles, ideas, strategies, theme_filter=theme_filter, limit=limit
    )
    return payload.model_dump()


__all__ = [
    "get_profile",
    "search_profiles",
    "get_ideas",
    "get_strategies",
    "get_evidence",
    "get_themes",
    "get_graph",
]