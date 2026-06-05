"""SQLAlchemy models for Open Org Phase 1.

Lives in its own module so the existing ``models.py`` (and its migration
history) stays untouched. Re-exported from ``models.py`` so the Alembic
``from llmstxt_api.models import *`` line picks up the new tables.

Storage decision (PLAN.md row 5): markdown is the canonical write surface;
JSON is derived on save. Both columns are stored. Round-trip identity is a
tested invariant of the converter.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from llmstxt_api.database import Base


class OrgProfile(Base):
    """An organisation's published Open Org profile.

    ``org_id`` is the org-id.guide identifier (e.g. ``GB-CHC-1234567``) and is
    the natural key used by other tables. The UUID ``id`` is for joins where
    a stable surrogate is preferred (history, versions, etc.).
    """

    __tablename__ = "org_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    markdown_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Profile generator (Step 5) state. ``pending`` is the initial value when
    # the row is created from POST /api/open-org/generate; the Celery task
    # transitions it to ``ready`` on success or ``failed`` (with
    # ``generation_error`` populated) on error.
    generation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # values: pending, generating, ready, failed
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Fine-grained generation progress, populated only during the first
    # 30-90s of an org's life. Powers the live-progress display on the
    # Generate page; safe to leave NULL on existing rows.
    generation_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    generation_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generation_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generation_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Murmurations index state
    murmurations_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    murmurations_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # values: pending, validated, posted, failed

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_org_profiles_org_id", "org_id"),
        Index("ix_org_profiles_published", "published"),
    )


class OrgStrategy(Base):
    """A strategy belonging to an organisation."""

    __tablename__ = "org_strategies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    markdown_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Themes denormalized for fast filtering on the discovery page.
    themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_org_strategies_org_slug"),
        Index("ix_org_strategies_org_id", "org_id"),
        Index("ix_org_strategies_status", "status"),
    )


class OrgIdea(Base):
    """An idea belonging to an organisation."""

    __tablename__ = "org_ideas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    markdown_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    idea_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="seed")
    themes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_org_ideas_org_slug"),
        Index("ix_org_ideas_org_id", "org_id"),
        Index("ix_org_ideas_status", "status"),
    )


class OrgVersion(Base):
    """Append-only audit trail of markdown snapshots, keyed by parent kind+id.

    Polymorphic by design — ``parent_kind`` distinguishes which of
    ``org_profiles`` / ``org_strategies`` / ``org_ideas`` the snapshot came
    from. Cross-table FKs are intentionally not enforced at the SQL level so
    deletes on the parent don't cascade-destroy history; treat this table as
    write-once.
    """

    __tablename__ = "org_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # values: profile, strategy, idea
    parent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    markdown_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_org_versions_parent", "parent_kind", "parent_id", "created_at"),
    )


class OrgAdmin(Base):
    """Authorises a user to edit a given org's profile/strategies/ideas.

    Composite PK on ``(user_id, org_id)``. ``role`` distinguishes ``owner``
    (can add/remove other admins) from ``editor`` (can edit content only).
    """

    __tablename__ = "org_admins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="editor")
    # values: owner, editor
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_org_admins_org_id", "org_id"),
    )


class CreatorSession(Base):
    """Server-side state for a strategy/idea chat creator session.

    Conversation history is stored as a JSON array of ``{role, content}``
    dicts. ``current_markdown`` is the live preview the chat is building up;
    on finalize it's copied to the corresponding ``org_strategies`` /
    ``org_ideas`` row.
    """

    __tablename__ = "creator_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # values: strategy, idea
    conversation_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    current_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_creator_sessions_org_id", "org_id"),
        Index("ix_creator_sessions_expires_at", "expires_at"),
    )


class LlmUsage(Base):
    """Per-feature, per-org Anthropic API usage log.

    Drives the £0.50/org/day soft cap (locked decision #10) and per-feature
    cost analytics. Cache token counts let us validate that prompt caching
    is actually saving money over time.
    """

    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    # values: profile_generator, strategy_creator, idea_creator, ...
    org_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_llm_usage_org_created", "org_id", "created_at"),
        Index("ix_llm_usage_feature_created", "feature", "created_at"),
    )


class ExternalOrgCache(Base):
    """Federated profiles pulled from the Murmurations index.

    Distinct from ``org_profiles`` because federated profiles aren't ours —
    we don't host them, can't edit them, and may evict them when they fall
    out of the index. Discovery queries union both tables.
    """

    __tablename__ = "external_org_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_external_org_cache_org_id", "org_id"),
        Index("ix_external_org_cache_last_synced", "last_synced_at"),
    )


__all__ = [
    "OrgProfile",
    "OrgStrategy",
    "OrgIdea",
    "OrgVersion",
    "OrgAdmin",
    "CreatorSession",
    "LlmUsage",
    "ExternalOrgCache",
]
