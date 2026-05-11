"""Add Open Org tables (Phase 1)

Adds 8 tables for the Open Org sub-application: org_profiles, org_strategies,
org_ideas, org_versions, org_admins, creator_sessions, llm_usage,
external_org_cache. See PLAN.md row 5 for the storage decision.

Revision ID: b1c2d3e4f5a6
Revises: 7b64d535033a
Create Date: 2026-05-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "7b64d535033a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False, unique=True),
        sa.Column("markdown_source", sa.Text(), nullable=True),
        sa.Column("profile_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("murmurations_node_id", sa.String(64), nullable=True),
        sa.Column(
            "murmurations_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_org_profiles_org_id", "org_profiles", ["org_id"])
    op.create_index("ix_org_profiles_published", "org_profiles", ["published"])

    op.create_table(
        "org_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("markdown_source", sa.Text(), nullable=True),
        sa.Column("strategy_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("themes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "slug", name="uq_org_strategies_org_slug"),
    )
    op.create_index("ix_org_strategies_org_id", "org_strategies", ["org_id"])
    op.create_index("ix_org_strategies_status", "org_strategies", ["status"])

    op.create_table(
        "org_ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("markdown_source", sa.Text(), nullable=True),
        sa.Column("idea_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="seed"),
        sa.Column("themes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("linked_strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "slug", name="uq_org_ideas_org_slug"),
    )
    op.create_index("ix_org_ideas_org_id", "org_ideas", ["org_id"])
    op.create_index("ix_org_ideas_status", "org_ideas", ["status"])

    op.create_table(
        "org_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_kind", sa.String(16), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("markdown_snapshot", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_org_versions_parent",
        "org_versions",
        ["parent_kind", "parent_id", "created_at"],
    )

    op.create_table(
        "org_admins",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("org_id", sa.String(64), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="editor"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_org_admins_org_id", "org_admins", ["org_id"])

    op.create_table(
        "creator_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("conversation_history", postgresql.JSONB(), nullable=True),
        sa.Column("current_markdown", sa.Text(), nullable=True),
        sa.Column(
            "last_active_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_creator_sessions_org_id", "creator_sessions", ["org_id"])
    op.create_index("ix_creator_sessions_expires_at", "creator_sessions", ["expires_at"])

    op.create_table(
        "llm_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_llm_usage_org_created", "llm_usage", ["org_id", "created_at"])
    op.create_index("ix_llm_usage_feature_created", "llm_usage", ["feature", "created_at"])

    op.create_table(
        "external_org_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False, unique=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("profile_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "last_synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_external_org_cache_org_id", "external_org_cache", ["org_id"])
    op.create_index(
        "ix_external_org_cache_last_synced",
        "external_org_cache",
        ["last_synced_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_org_cache_last_synced", table_name="external_org_cache")
    op.drop_index("ix_external_org_cache_org_id", table_name="external_org_cache")
    op.drop_table("external_org_cache")

    op.drop_index("ix_llm_usage_feature_created", table_name="llm_usage")
    op.drop_index("ix_llm_usage_org_created", table_name="llm_usage")
    op.drop_table("llm_usage")

    op.drop_index("ix_creator_sessions_expires_at", table_name="creator_sessions")
    op.drop_index("ix_creator_sessions_org_id", table_name="creator_sessions")
    op.drop_table("creator_sessions")

    op.drop_index("ix_org_admins_org_id", table_name="org_admins")
    op.drop_table("org_admins")

    op.drop_index("ix_org_versions_parent", table_name="org_versions")
    op.drop_table("org_versions")

    op.drop_index("ix_org_ideas_status", table_name="org_ideas")
    op.drop_index("ix_org_ideas_org_id", table_name="org_ideas")
    op.drop_table("org_ideas")

    op.drop_index("ix_org_strategies_status", table_name="org_strategies")
    op.drop_index("ix_org_strategies_org_id", table_name="org_strategies")
    op.drop_table("org_strategies")

    op.drop_index("ix_org_profiles_published", table_name="org_profiles")
    op.drop_index("ix_org_profiles_org_id", table_name="org_profiles")
    op.drop_table("org_profiles")
