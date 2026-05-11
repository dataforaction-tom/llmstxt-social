"""Admin edit routes for Open Org profiles, strategies, and ideas.

Markdown is the canonical write surface (PLAN.md row 5). Every PUT runs the
markdown through the converter, validates the derived JSON against the
schema, writes both columns on success, and snapshots the new markdown to
``org_versions`` for audit/restore.

Auth: gated by :func:`llmstxt_api.routes.open_org_auth.require_org_admin`.
Routes mount under ``/api/open-org`` to keep them clearly distinct from the
public profile URLs at ``/open-org``.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import (
    OrgAdmin,
    OrgIdea,
    OrgProfile,
    OrgStrategy,
    OrgVersion,
)
from llmstxt_api.routes.open_org_auth import require_org_admin
from llmstxt_api.tasks.open_org_murmurations import (
    delete_from_murmurations_task,
    submit_to_murmurations_task,
)
from llmstxt_core.open_org.converter import ConverterError, markdown_to_json


router = APIRouter(prefix="/api/open-org", tags=["open-org-admin"])


class MarkdownPayload(BaseModel):
    markdown: str = Field(..., description="Full markdown source with YAML frontmatter")


class SaveResponse(BaseModel):
    saved: bool
    org_id: str
    schema_kind: Literal["profile", "strategy", "idea"]


class MarkdownResponse(BaseModel):
    markdown: str
    org_id: str
    schema_kind: Literal["profile", "strategy", "idea"]


class PublishResponse(BaseModel):
    org_id: str
    published: bool
    submission_task_id: str | None = None


class UnpublishResponse(BaseModel):
    org_id: str
    published: bool
    delete_task_id: str | None = None


class VersionListEntry(BaseModel):
    id: uuid.UUID
    parent_kind: str
    parent_id: uuid.UUID
    created_at: str
    created_by_user_id: uuid.UUID | None = None


class VersionList(BaseModel):
    org_id: str
    versions: list[VersionListEntry]


# --- helpers ---------------------------------------------------------------

def _converter_error_to_http(err: ConverterError) -> HTTPException:
    """Turn a ConverterError into a 400 with structured field errors."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"errors": err.errors},
    )


async def _snapshot_version(
    db: AsyncSession,
    *,
    parent_kind: str,
    parent_id: uuid.UUID,
    markdown_snapshot: str,
    user_id: uuid.UUID | None,
) -> OrgVersion:
    version = OrgVersion(
        parent_kind=parent_kind,
        parent_id=parent_id,
        markdown_snapshot=markdown_snapshot,
        created_by_user_id=user_id,
    )
    db.add(version)
    return version


# --- profile ---------------------------------------------------------------

@router.get("/{org_id}/profile.md", response_model=MarkdownResponse)
async def get_profile_markdown(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return MarkdownResponse(
        markdown=profile.markdown_source or "",
        org_id=org_id,
        schema_kind="profile",
    )


@router.put("/{org_id}/profile.md", response_model=SaveResponse)
async def put_profile_markdown(
    org_id: str,
    payload: MarkdownPayload,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    try:
        derived = markdown_to_json(payload.markdown, kind="profile")
    except ConverterError as e:
        raise _converter_error_to_http(e) from e

    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = OrgProfile(org_id=org_id)
        db.add(profile)
        # New profile has no prior history — snapshot creation as v1.
    profile.markdown_source = payload.markdown
    profile.profile_json = derived

    await _snapshot_version(
        db,
        parent_kind="profile",
        parent_id=profile.id,
        markdown_snapshot=payload.markdown,
        user_id=admin.user_id,
    )

    await db.commit()

    # Re-submit on edit so the Murmurations index stays in sync with the
    # public URL. Only fires for profiles that are already published — drafts
    # don't get indexed until the owner explicitly clicks Publish.
    if profile.published and profile.profile_json:
        submit_to_murmurations_task.delay(profile_id=str(profile.id))

    return SaveResponse(saved=True, org_id=org_id, schema_kind="profile")


# --- strategy --------------------------------------------------------------

@router.get("/{org_id}/strategies/{slug}.md", response_model=MarkdownResponse)
async def get_strategy_markdown(
    org_id: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id, OrgStrategy.slug == slug
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=404, detail="strategy not found")
    return MarkdownResponse(
        markdown=strategy.markdown_source or "",
        org_id=org_id,
        schema_kind="strategy",
    )


@router.put("/{org_id}/strategies/{slug}.md", response_model=SaveResponse)
async def put_strategy_markdown(
    org_id: str,
    slug: str,
    payload: MarkdownPayload,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    try:
        derived = markdown_to_json(payload.markdown, kind="strategy")
    except ConverterError as e:
        raise _converter_error_to_http(e) from e

    result = await db.execute(
        select(OrgStrategy).where(
            OrgStrategy.org_id == org_id, OrgStrategy.slug == slug
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        strategy = OrgStrategy(org_id=org_id, slug=slug)
        db.add(strategy)
    strategy.markdown_source = payload.markdown
    strategy.strategy_json = derived
    strategy.status = derived.get("status", strategy.status)
    strategy.themes = derived.get("themes")

    await _snapshot_version(
        db,
        parent_kind="strategy",
        parent_id=strategy.id,
        markdown_snapshot=payload.markdown,
        user_id=admin.user_id,
    )

    await db.commit()
    return SaveResponse(saved=True, org_id=org_id, schema_kind="strategy")


# --- idea ------------------------------------------------------------------

@router.get("/{org_id}/ideas/{slug}.md", response_model=MarkdownResponse)
async def get_idea_markdown(
    org_id: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    result = await db.execute(
        select(OrgIdea).where(OrgIdea.org_id == org_id, OrgIdea.slug == slug)
    )
    idea = result.scalar_one_or_none()
    if idea is None:
        raise HTTPException(status_code=404, detail="idea not found")
    return MarkdownResponse(
        markdown=idea.markdown_source or "",
        org_id=org_id,
        schema_kind="idea",
    )


@router.put("/{org_id}/ideas/{slug}.md", response_model=SaveResponse)
async def put_idea_markdown(
    org_id: str,
    slug: str,
    payload: MarkdownPayload,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    try:
        derived = markdown_to_json(payload.markdown, kind="idea")
    except ConverterError as e:
        raise _converter_error_to_http(e) from e

    result = await db.execute(
        select(OrgIdea).where(OrgIdea.org_id == org_id, OrgIdea.slug == slug)
    )
    idea = result.scalar_one_or_none()
    if idea is None:
        idea = OrgIdea(org_id=org_id, slug=slug)
        db.add(idea)
    idea.markdown_source = payload.markdown
    idea.idea_json = derived
    idea.status = derived.get("status", idea.status)
    idea.themes = derived.get("themes")

    await _snapshot_version(
        db,
        parent_kind="idea",
        parent_id=idea.id,
        markdown_snapshot=payload.markdown,
        user_id=admin.user_id,
    )

    await db.commit()
    return SaveResponse(saved=True, org_id=org_id, schema_kind="idea")


# --- history --------------------------------------------------------------

@router.get("/{org_id}/history", response_model=VersionList)
async def list_history(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    # Scope by the org's profile (the parent_id we filter on). Strategies
    # and ideas have their own parent_ids — for Phase 1 the history endpoint
    # returns profile-scoped versions; strategy/idea history can be added
    # per-record later if needed.
    profile_result = await db.execute(
        select(OrgProfile).where(OrgProfile.org_id == org_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")

    versions_result = await db.execute(
        select(OrgVersion)
        .where(
            OrgVersion.parent_kind == "profile",
            OrgVersion.parent_id == profile.id,
        )
        .order_by(OrgVersion.created_at.desc())
    )
    versions = versions_result.scalars().all()
    return VersionList(
        org_id=org_id,
        versions=[
            VersionListEntry(
                id=v.id,
                parent_kind=v.parent_kind,
                parent_id=v.parent_id,
                created_at=v.created_at.isoformat() if v.created_at else "",
                created_by_user_id=v.created_by_user_id,
            )
            for v in versions
        ],
    )


# --- publish ---------------------------------------------------------------

@router.post("/{org_id}/publish", response_model=PublishResponse)
async def publish_profile(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    """Flip ``published=True`` and dispatch a Murmurations submission."""
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    if not profile.profile_json:
        # Can't publish an empty profile — the public URL would 404 and the
        # index would have nothing to fetch.
        raise HTTPException(
            status_code=400,
            detail="profile has no content yet; save markdown before publishing",
        )

    profile.published = True
    await db.commit()

    handle = submit_to_murmurations_task.delay(profile_id=str(profile.id))
    return PublishResponse(
        org_id=org_id,
        published=True,
        submission_task_id=getattr(handle, "id", None),
    )


# --- unpublish -------------------------------------------------------------

@router.post("/{org_id}/unpublish", response_model=UnpublishResponse)
async def unpublish_profile(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
):
    """Flip ``published=False`` and remove the Murmurations index node.

    Hides the public profile JSON immediately; the federated cache catches
    up via the daily sync, but the index node is deleted right away so
    discovery clients don't keep linking to a profile we no longer serve.
    """
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")

    profile.published = False
    await db.commit()

    delete_task_id: str | None = None
    if profile.murmurations_node_id:
        handle = delete_from_murmurations_task.delay(profile_id=str(profile.id))
        delete_task_id = getattr(handle, "id", None)

    return UnpublishResponse(
        org_id=org_id,
        published=False,
        delete_task_id=delete_task_id,
    )
