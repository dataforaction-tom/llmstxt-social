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
from llmstxt_api.open_org_models import (
    OrgIdea,
    OrgProfile,
    OrgStrategy,
    OrgVersion,
)


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
    summaries = [
        _record_summary(r.slug, r.themes, r.status, r.strategy_json, r.created_at, r.updated_at)
        for r in rows
    ]
    return Response(
        content=_json_list_body(summaries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/ideas")
async def list_ideas(org_id: str, db: AsyncSession = Depends(get_db)):
    """List published ideas for an org as a JSON array of summaries.

    Each entry: ``{slug, themes, status, summary?, created_at, updated_at}``.
    Same envelope shape as the strategies list.
    """
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgIdea)
        .where(OrgIdea.org_id == org_id, OrgIdea.published.is_(True))
        .order_by(OrgIdea.created_at.desc())
    )
    rows = result.scalars().all()
    summaries = [
        _record_summary(r.slug, r.themes, r.status, r.idea_json, r.created_at, r.updated_at)
        for r in rows
    ]
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


# --- version history (public, no auth) -------------------------------------
#
# "Trajectory not snapshot" (tomcw.xyz/the-grant-application-is-dead):
# funders should see how the org evolved over time, not just its current
# state. The OrgVersion table holds append-only markdown snapshots keyed
# by parent_kind (profile/strategy/idea) + parent_id. These endpoints
# surface that audit trail publicly, gated behind the same published-flag
# existence-leak rules as the rest of the public API.


@router.get("/{org_id}/history")
async def list_org_history(org_id: str, db: AsyncSession = Depends(get_db)):
    """Chronological list of version snapshots for the org's profile,
    strategies, and ideas — most recent first.

    Each entry: ``{timestamp, parent_kind, parent_slug, summary}``.
    ``parent_slug`` is ``null`` for profile snapshots. ``summary`` is the
    first ~200 chars of the snapshot body (after the YAML front matter) or
    a status-change description when one can be detected.

    404s if the parent profile isn't published.
    """
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")

    # Collect the parent ids for strategies and ideas so we can map
    # OrgVersion.parent_id → a slug for the response.
    strat_result = await db.execute(
        select(OrgStrategy).where(OrgStrategy.org_id == org_id)
    )
    strategies = strat_result.scalars().all()
    idea_result = await db.execute(
        select(OrgIdea).where(OrgIdea.org_id == org_id)
    )
    ideas = idea_result.scalars().all()

    slug_by_id: dict[object, str] = {s.id: s.slug for s in strategies}
    slug_by_id.update({i.id: i.slug for i in ideas})

    versions_result = await db.execute(
        select(OrgVersion)
        .where(OrgVersion.parent_kind.in_(("profile", "strategy", "idea")))
        .order_by(OrgVersion.created_at.desc())
    )
    versions = versions_result.scalars().all()

    entries = [
        _history_entry(v, slug_by_id.get(v.parent_id))
        for v in versions
    ]
    # Sort defensively in case the DB didn't honour the ORDER BY (e.g. mocked
    # sessions in tests return the rows in insertion order).
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return Response(
        content=_json_list_body(entries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


@router.get("/{org_id}/strategies/{slug}/history")
async def list_strategy_history(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    """Version snapshots for one strategy, most recent first.

    404s if the parent profile is unpublished or the strategy is missing /
    unpublished — same existence-leak rules as the per-record JSON route.
    """
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id,
            OrgStrategy.slug == slug,
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None or not strategy.published:
        raise HTTPException(status_code=404, detail="strategy not found")
    return await _record_history_response(db, "strategy", strategy.id, slug)


@router.get("/{org_id}/ideas/{slug}/history")
async def list_idea_history(
    org_id: str, slug: str, db: AsyncSession = Depends(get_db)
):
    """Version snapshots for one idea, most recent first."""
    if not await _profile_is_published(db, org_id):
        raise HTTPException(status_code=404, detail="profile not found")
    result = await db.execute(
        select(OrgIdea).where(
            OrgIdea.org_id == org_id,
            OrgIdea.slug == slug,
        )
    )
    idea = result.scalar_one_or_none()
    if idea is None or not idea.published:
        raise HTTPException(status_code=404, detail="idea not found")
    return await _record_history_response(db, "idea", idea.id, slug)


async def _record_history_response(
    db: AsyncSession, parent_kind: str, parent_id: object, slug: str
) -> Response:
    versions_result = await db.execute(
        select(OrgVersion)
        .where(
            OrgVersion.parent_kind == parent_kind,
            OrgVersion.parent_id == parent_id,
        )
        .order_by(OrgVersion.created_at.desc())
    )
    versions = versions_result.scalars().all()
    entries = [_history_entry(v, slug) for v in versions]
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return Response(
        content=_json_list_body(entries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


def _history_entry(version: OrgVersion, parent_slug: str | None) -> dict:
    return {
        "timestamp": _isoformat(version.created_at) if version.created_at else "",
        "parent_kind": version.parent_kind,
        "parent_slug": parent_slug,
        "summary": _snapshot_summary(version.markdown_snapshot or "", version.parent_kind),
    }


def _snapshot_summary(markdown: str, parent_kind: str) -> str:
    """Extract a one-line summary from a markdown snapshot.

    Strips YAML front matter, then takes the first ~200 chars of the body
    with whitespace collapsed. If the body contains a ``## Summary`` section
    its first line is preferred. A ``status:`` line in the front matter is
    surfaced as "Status changed to <value>" when present.
    """
    import re

    # Pull a status line out of the front matter if there is one.
    fm_match = re.match(r"^---\s*\n(.*?\n)---\s*\n", markdown, re.DOTALL)
    front_matter = fm_match.group(1) if fm_match else ""
    body = markdown[fm_match.end():] if fm_match else markdown

    status_match = re.search(r"^status:\s*(\w+)\s*$", front_matter, re.MULTILINE)
    if status_match:
        return f"{parent_kind.capitalize()} status changed to {status_match.group(1)}"

    # Prefer the first line of a ## Summary section.
    summary_match = re.search(
        r"^##\s*Summary\s*\n\s*(.+)$", body, re.MULTILINE
    )
    if summary_match:
        return _collapse(summary_match.group(1))[:200]

    # Fall back to the first non-empty, non-heading line of the body.
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return _collapse(stripped)[:200]
    return _collapse(body.strip())[:200]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _record_summary(
    slug: str,
    themes: list[str] | None,
    status: str | None,
    record_json: dict | None,
    created_at: object | None = None,
    updated_at: object | None = None,
) -> dict:
    summary_text = ""
    title_text = ""
    if isinstance(record_json, dict):
        candidate = record_json.get("summary")
        if isinstance(candidate, str):
            summary_text = candidate.strip()[:280]
        title_candidate = record_json.get("title")
        if isinstance(title_candidate, str):
            title_text = title_candidate.strip()
    entry: dict = {
        "slug": slug,
        "themes": list(themes or []),
    }
    if title_text:
        entry["title"] = title_text
    if status:
        entry["status"] = status
    if summary_text:
        entry["summary"] = summary_text
    if created_at is not None:
        entry["created_at"] = _isoformat(created_at)
    if updated_at is not None:
        entry["updated_at"] = _isoformat(updated_at)
    return entry


def _isoformat(value: object) -> str:
    """Safely render a datetime (or string) as ISO-8601, no timezone suffix."""
    from datetime import datetime
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_response_body(payload: dict | None) -> bytes:
    """Serialize a JSONB column to bytes. Empty payload renders as ``{}``."""
    import json
    return json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")


def _json_list_body(items: list[dict]) -> bytes:
    import json
    return json.dumps(items, ensure_ascii=False).encode("utf-8")
