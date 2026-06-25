"""Public discovery routes for Open Org.

Two endpoints, both unauthenticated:

* ``GET /api/open-org/themes`` — controlled vocabulary used by the filter UI.
* ``GET /api/open-org/discover`` — paginated union of local published profiles
  and the federated cache.

The discovery endpoint is the entry point for funders and peer organisations,
so it stays public and edge-cacheable. Local profiles are authoritative for
their org; federated rows come from the daily Murmurations sync.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import ExternalOrgCache, OrgIdea, OrgProfile, OrgStrategy
from llmstxt_core.open_org.themes import load_themes


router = APIRouter(prefix="/api/open-org", tags=["open-org-discovery"])


# 30-minute browser cache for the themes endpoint; vocabulary is stable across
# the day. Cloudflare edge can layer more on top.
_THEMES_CACHE = "public, max-age=1800"

# Discovery responses are short-cached so the federated picture stays fresh
# but every visitor doesn't hit the DB.
_DISCOVER_CACHE = "public, max-age=60"


# ---------------------------------------------------------------------------
# Themes vocabulary
# ---------------------------------------------------------------------------


@router.get("/themes")
def get_themes() -> Response:
    body = json.dumps(load_themes(), ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={"Cache-Control": _THEMES_CACHE},
    )


# ---------------------------------------------------------------------------
# Discovery row + pagination
# ---------------------------------------------------------------------------


class DiscoveryRow(BaseModel):
    org_id: str
    name: str
    summary: str | None = None
    themes: list[str] = Field(default_factory=list)
    primary_area: str | None = None
    primary_area_code: str | None = None
    geolocation: dict | None = None
    profile_url: str
    source: str  # "local" | "federated"


class DiscoveryPage(BaseModel):
    results: list[DiscoveryRow]
    next_cursor: str | None = None


def _encode_cursor(name: str, org_id: str) -> str:
    payload = json.dumps({"n": name, "o": org_id}, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        return str(payload["n"]), str(payload["o"])
    except Exception:  # noqa: BLE001
        # An unparseable cursor returns the first page rather than erroring —
        # avoids one bad querystring breaking the whole feature.
        return None


def _local_to_row(profile: OrgProfile) -> DiscoveryRow | None:
    payload = profile.profile_json or {}
    identity = payload.get("identity") or {}
    mission = payload.get("mission") or {}
    name = identity.get("name")
    if not isinstance(name, str) or not name:
        return None
    geography = identity.get("geography") or {}
    geolocation = geography.get("geolocation")
    return DiscoveryRow(
        org_id=profile.org_id,
        name=name,
        summary=(mission.get("summary") if isinstance(mission.get("summary"), str) else None),
        themes=list(mission.get("themes") or []),
        primary_area=geography.get("primary_area"),
        primary_area_code=geography.get("primary_area_code"),
        geolocation=geolocation if isinstance(geolocation, dict) else None,
        profile_url=f"/open-org/{profile.org_id}/profile.json",
        source="local",
    )


def _external_to_row(row: ExternalOrgCache) -> DiscoveryRow | None:
    payload = row.profile_json or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return None
    geolocation = payload.get("geolocation")
    profile_url = payload.get("open_org_profile_url") or row.source_url
    return DiscoveryRow(
        org_id=row.org_id,
        name=name,
        summary=None,  # Envelope shape has no plain-text summary; future schemas might.
        themes=list(payload.get("tags") or []),
        primary_area=payload.get("primary_area"),
        primary_area_code=payload.get("primary_area_code"),
        geolocation=geolocation if isinstance(geolocation, dict) else None,
        profile_url=profile_url,
        source="federated",
    )


def _matches_filters(
    row: DiscoveryRow,
    *,
    theme: str | None,
    area_code: str | None,
    q: str | None,
) -> bool:
    if theme and theme not in row.themes:
        return False
    if area_code and row.primary_area_code != area_code:
        return False
    if q:
        haystack = " ".join(filter(None, [row.name, row.primary_area, row.summary or ""])).lower()
        if q.lower() not in haystack:
            return False
    return True


# ---------------------------------------------------------------------------
# Discover endpoint
# ---------------------------------------------------------------------------


@router.get("/discover", response_model=DiscoveryPage)
async def discover(
    theme: str | None = Query(default=None, description="Open Org theme key filter"),
    area_code: str | None = Query(default=None, description="ONS LAD/ITL code filter"),
    q: str | None = Query(default=None, description="Free-text search across name/area/summary"),
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Response:
    rows = await _gather_rows(db, theme=theme, area_code=area_code, q=q)

    # Stable order: name then org_id, both case-insensitive on name.
    rows.sort(key=lambda r: (r.name.casefold(), r.org_id))

    after = _decode_cursor(cursor)
    if after is not None:
        cutoff_name, cutoff_org = after
        rows = [
            r for r in rows
            if (r.name.casefold(), r.org_id) > (cutoff_name.casefold(), cutoff_org)
        ]

    page = rows[:limit]
    next_cursor: str | None = None
    if len(page) == limit and len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(last.name, last.org_id)

    payload = DiscoveryPage(results=page, next_cursor=next_cursor)
    return Response(
        content=payload.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _DISCOVER_CACHE},
    )


async def _gather_rows(
    db: AsyncSession,
    *,
    theme: str | None,
    area_code: str | None,
    q: str | None,
) -> list[DiscoveryRow]:
    """Return the merged list of DiscoveryRow objects after coarse server-side
    filtering. We still apply Python-side filters in :func:`_matches_filters`
    because JSONB filtering only narrows the candidate set."""
    local_query = select(OrgProfile).where(OrgProfile.published.is_(True))
    external_query = select(ExternalOrgCache)

    if theme:
        # JSONB array containment: mission.themes ? 'education'
        local_query = local_query.where(
            OrgProfile.profile_json["mission"]["themes"].op("?")(theme)
        )
        external_query = external_query.where(
            ExternalOrgCache.profile_json["tags"].op("?")(theme)
        )

    if q:
        like = f"%{q.lower()}%"
        # Match against the JSONB ``name`` for both tables. JSONB ``->>`` returns
        # text; ILIKE handles the case-insensitive part.
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

    discovery_rows: list[DiscoveryRow] = []
    for profile in local_rows:
        row = _local_to_row(profile)
        if row and _matches_filters(row, theme=theme, area_code=area_code, q=q):
            discovery_rows.append(row)
    seen_org_ids = {r.org_id for r in discovery_rows}
    for cached in external_rows:
        row = _external_to_row(cached)
        if row is None:
            continue
        # Local profile wins when both sides have the same org_id.
        if row.org_id in seen_org_ids:
            continue
        if _matches_filters(row, theme=theme, area_code=area_code, q=q):
            discovery_rows.append(row)
    return discovery_rows


# ---------------------------------------------------------------------------
# Idea browser — cross-org list of published ideas
# ---------------------------------------------------------------------------


class IdeaRow(BaseModel):
    org_id: str
    org_name: str
    slug: str
    summary: str | None = None
    themes: list[str] = Field(default_factory=list)
    status: str | None = None
    primary_area: str | None = None
    cost_lower: int | None = None
    cost_upper: int | None = None
    cost_currency: str | None = None
    idea_url: str  # /open-org/{org_id}/ideas/{slug}.json
    profile_url: str  # /openorg/{org_id} — human-readable page


class IdeaPage(BaseModel):
    results: list[IdeaRow]
    next_cursor: str | None = None


@router.get("/discover/ideas", response_model=IdeaPage)
async def discover_ideas(
    theme: str | None = Query(default=None),
    area_code: str | None = Query(default=None),
    status: str | None = Query(default=None, description="seed|developing|active|done"),
    q: str | None = Query(default=None, description="Free-text search across slug + summary"),
    cost_max: int | None = Query(default=None, ge=0, description="Filter to ideas whose lower cost is ≤ this (GBP)"),
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Cross-org list of published ideas. Joins each idea against its parent
    profile so unpublished profiles don't expose orphan ideas. Theme / status
    filters narrow at the DB layer; cost-range and free-text are applied
    in-memory since the JSONB shape varies."""
    idea_q = select(OrgIdea).where(OrgIdea.published.is_(True))
    if theme:
        idea_q = idea_q.where(OrgIdea.themes.op("?")(theme))
    if status:
        idea_q = idea_q.where(OrgIdea.status == status)

    ideas = (await db.execute(idea_q)).scalars().all()
    if not ideas:
        return _idea_page_response([], None)

    org_ids = {i.org_id for i in ideas}
    profiles = (
        await db.execute(
            select(OrgProfile).where(
                OrgProfile.org_id.in_(org_ids),
                OrgProfile.published.is_(True),
            )
        )
    ).scalars().all()
    by_org: dict[str, OrgProfile] = {p.org_id: p for p in profiles}

    rows: list[IdeaRow] = []
    for idea in ideas:
        profile = by_org.get(idea.org_id)
        if profile is None:
            continue  # parent profile unpublished — don't surface orphan idea
        row = _idea_to_row(idea, profile)
        if not _matches_idea_filters(row, q=q, area_code=area_code, cost_max=cost_max):
            continue
        rows.append(row)

    rows.sort(key=lambda r: (r.org_name.casefold(), r.slug))
    after = _decode_cursor(cursor)
    if after is not None:
        cutoff_org, cutoff_slug = after
        rows = [
            r for r in rows
            if (r.org_name.casefold(), r.slug) > (cutoff_org.casefold(), cutoff_slug)
        ]

    page = rows[:limit]
    next_cursor: str | None = None
    if len(page) == limit and len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(last.org_name, last.slug)

    return _idea_page_response(page, next_cursor)


def _idea_page_response(results: list[IdeaRow], next_cursor: str | None) -> Response:
    payload = IdeaPage(results=results, next_cursor=next_cursor)
    return Response(
        content=payload.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _DISCOVER_CACHE},
    )


def _idea_to_row(idea: OrgIdea, profile: OrgProfile) -> IdeaRow:
    idea_payload = idea.idea_json or {}
    profile_payload = profile.profile_json or {}
    identity = profile_payload.get("identity") or {}
    geography = identity.get("geography") or {}

    summary = idea_payload.get("summary") if isinstance(idea_payload.get("summary"), str) else None

    cost = idea_payload.get("indicative_cost") or {}
    cost_lower = cost.get("lower") if isinstance(cost.get("lower"), int) else None
    cost_upper = cost.get("upper") if isinstance(cost.get("upper"), int) else None
    cost_currency = cost.get("currency") if isinstance(cost.get("currency"), str) else None

    return IdeaRow(
        org_id=idea.org_id,
        org_name=identity.get("name") or idea.org_id,
        slug=idea.slug,
        summary=summary[:280] if summary else None,
        themes=list(idea.themes or []),
        status=idea.status,
        primary_area=geography.get("primary_area"),
        cost_lower=cost_lower,
        cost_upper=cost_upper,
        cost_currency=cost_currency,
        idea_url=f"/open-org/{idea.org_id}/ideas/{idea.slug}.json",
        profile_url=f"/openorg/{idea.org_id}",
    )


def _matches_idea_filters(
    row: IdeaRow,
    *,
    q: str | None,
    area_code: str | None,
    cost_max: int | None,
) -> bool:
    if q:
        haystack = " ".join(filter(None, [row.org_name, row.slug, row.summary or ""])).lower()
        if q.lower() not in haystack:
            return False
    if area_code:
        # area_code filter requires a precise match on the org's primary_area_code;
        # we don't have that on IdeaRow yet, so this filter is currently a no-op
        # on local rows. Future Phase 2 work: surface primary_area_code on the row.
        pass
    if cost_max is not None and row.cost_lower is not None:
        if row.cost_lower > cost_max:
            return False
    return True


# ---------------------------------------------------------------------------
# Graph endpoint — nodes + edges for the discovery visualisation
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    id: str
    type: str  # "organisation" | "idea" | "strategy"
    name: str
    themes: list[str] = Field(default_factory=list)
    # organisation-only
    area: str | None = None
    income_band: str | None = None
    ideas_count: int | None = None
    strategy_themes: list[str] = Field(default_factory=list)
    # idea/strategy-only
    org_id: str | None = None
    cost_range: list[int] | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "org_idea" | "org_strategy" | "shared_theme" | "shared_area"
    weight: int | None = None


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def _profile_themes(profile: OrgProfile) -> list[str]:
    payload = profile.profile_json or {}
    mission = payload.get("mission") or {}
    themes = mission.get("themes")
    return list(themes) if isinstance(themes, list) else []


def _profile_area(profile: OrgProfile) -> str | None:
    payload = profile.profile_json or {}
    identity = payload.get("identity") or {}
    geography = identity.get("geography") or {}
    area = geography.get("primary_area")
    return area if isinstance(area, str) else None


def _profile_income_band(profile: OrgProfile) -> str | None:
    payload = profile.profile_json or {}
    identity = payload.get("identity") or {}
    scale = identity.get("scale") or {}
    band = scale.get("annual_income_band")
    return band if isinstance(band, str) else None


def _idea_name(idea: OrgIdea) -> str:
    payload = idea.idea_json or {}
    title = payload.get("title")
    if isinstance(title, str) and title:
        return title
    return idea.slug


def _idea_cost_range(idea: OrgIdea) -> list[int] | None:
    payload = idea.idea_json or {}
    cost = payload.get("indicative_cost") or {}
    lower = cost.get("lower")
    upper = cost.get("upper")
    if isinstance(lower, int) and isinstance(upper, int):
        return [lower, upper]
    if isinstance(lower, int):
        return [lower, lower]
    if isinstance(upper, int):
        return [upper, upper]
    return None


def _strategy_name(strategy: OrgStrategy) -> str:
    payload = strategy.strategy_json or {}
    title = payload.get("title")
    if isinstance(title, str) and title:
        return title
    return strategy.slug


def _strategy_themes(strategy: OrgStrategy) -> list[str]:
    return list(strategy.themes or [])


@router.get("/graph", response_model=GraphPayload)
async def graph(
    themes: str | None = Query(
        default=None,
        description="Comma-separated theme keys; only nodes matching at least one are included",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max organisation nodes"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return a graph of organisations, ideas, and strategies with edges for
    direct ownership and shared themes / areas. Public, no auth."""
    theme_filter: set[str] | None = None
    if themes:
        # Accept either a comma-separated string (the wire format) or a list
        # (direct calls in tests).
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
    return Response(
        content=payload.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": _DISCOVER_CACHE},
    )


def _build_graph(
    profiles: list[OrgProfile],
    ideas: list[OrgIdea],
    strategies: list[OrgStrategy],
    *,
    theme_filter: set[str] | None,
    limit: int,
) -> GraphPayload:
    # Apply limit to organisation nodes (sorted by name for determinism).
    sorted_profiles = sorted(
        profiles, key=lambda p: (
            ((p.profile_json or {}).get("identity") or {}).get("name") or p.org_id
        )
    )[:limit]
    profile_org_ids = {p.org_id for p in sorted_profiles}

    def _matches_themes(node_themes: list[str]) -> bool:
        if theme_filter is None:
            return True
        return bool(set(node_themes) & theme_filter)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # Idea nodes keyed by org_id for ideas_count and strategy_themes.
    ideas_by_org: dict[str, list[OrgIdea]] = {}
    for idea in ideas:
        if idea.org_id not in profile_org_ids:
            continue
        idea_themes = list(idea.themes or [])
        if not _matches_themes(idea_themes):
            continue
        ideas_by_org.setdefault(idea.org_id, []).append(idea)
        nodes.append(GraphNode(
            id=f"idea:{idea.org_id}:{idea.slug}",
            type="idea",
            name=_idea_name(idea),
            themes=idea_themes,
            org_id=idea.org_id,
            cost_range=_idea_cost_range(idea),
        ))
        edges.append(GraphEdge(
            source=idea.org_id,
            target=f"idea:{idea.org_id}:{idea.slug}",
            type="org_idea",
        ))

    strategy_themes_by_org: dict[str, list[str]] = {}
    for strategy in strategies:
        if strategy.org_id not in profile_org_ids:
            continue
        strat_themes = _strategy_themes(strategy)
        if not _matches_themes(strat_themes):
            continue
        strategy_themes_by_org.setdefault(strategy.org_id, []).extend(strat_themes)
        nodes.append(GraphNode(
            id=f"strategy:{strategy.org_id}:{strategy.slug}",
            type="strategy",
            name=_strategy_name(strategy),
            themes=strat_themes,
            org_id=strategy.org_id,
        ))
        edges.append(GraphEdge(
            source=strategy.org_id,
            target=f"strategy:{strategy.org_id}:{strategy.slug}",
            type="org_strategy",
        ))

    # Organisation nodes — must match theme filter (against profile themes OR
    # its ideas/strategies themes that survived filtering, so an org whose only
    # matching theme is on an idea still appears).
    for profile in sorted_profiles:
        profile_themes = _profile_themes(profile)
        org_idea_themes = [
            t for idea in ideas_by_org.get(profile.org_id, [])
            for t in (idea.themes or [])
        ]
        org_strategy_themes = strategy_themes_by_org.get(profile.org_id, [])
        all_org_themes = set(profile_themes) | set(org_idea_themes) | set(org_strategy_themes)
        if theme_filter is not None and not (all_org_themes & theme_filter):
            continue
        nodes.append(GraphNode(
            id=profile.org_id,
            type="organisation",
            name=((profile.profile_json or {}).get("identity") or {}).get("name") or profile.org_id,
            themes=profile_themes,
            area=_profile_area(profile),
            income_band=_profile_income_band(profile),
            ideas_count=len(ideas_by_org.get(profile.org_id, [])),
            strategy_themes=list(set(org_strategy_themes)),
        ))

    # Org-org edges: shared themes and shared area.
    org_nodes = [n for n in nodes if n.type == "organisation"]
    for i, a in enumerate(org_nodes):
        a_themes = set(a.themes)
        a_area = a.area
        for b in org_nodes[i + 1:]:
            shared = a_themes & set(b.themes)
            if shared:
                edges.append(GraphEdge(
                    source=a.id, target=b.id, type="shared_theme", weight=len(shared),
                ))
            if a_area and b.area and a_area == b.area:
                edges.append(GraphEdge(
                    source=a.id, target=b.id, type="shared_area", weight=1,
                ))

    # Sort for deterministic output.
    nodes.sort(key=lambda n: n.id)
    edges.sort(key=lambda e: (e.source, e.target, e.type))
    return GraphPayload(nodes=nodes, edges=edges)


__all__ = [
    "DiscoveryPage",
    "DiscoveryRow",
    "GraphPayload",
    "GraphNode",
    "GraphEdge",
    "IdeaPage",
    "IdeaRow",
    "discover",
    "discover_ideas",
    "get_themes",
    "graph",
    "router",
]
