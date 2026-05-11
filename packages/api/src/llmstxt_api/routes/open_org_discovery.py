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
from llmstxt_api.open_org_models import ExternalOrgCache, OrgProfile
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


__all__ = [
    "DiscoveryPage",
    "DiscoveryRow",
    "discover",
    "get_themes",
    "router",
]
