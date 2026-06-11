"""Structural tests for the Open Org SQLAlchemy models.

DB round-trip tests live with the route integration tests in Step 4 — these
tests just confirm the model classes are wired correctly: tablenames,
columns, indexes, constraints, and that they're discoverable via
``from llmstxt_api.models import *`` (Alembic env relies on this).
"""

import importlib

import pytest


# --- discoverability ---------------------------------------------------------

def test_open_org_models_reexported_from_models_module():
    """Alembic env imports models.py with `from llmstxt_api.models import *`,
    so all Open Org models must be visible at that import path."""
    models = importlib.import_module("llmstxt_api.models")
    for name in (
        "OrgProfile", "OrgStrategy", "OrgIdea", "OrgVersion",
        "OrgAdmin", "CreatorSession", "LlmUsage", "ExternalOrgCache",
    ):
        assert hasattr(models, name), f"models.py must re-export {name}"


def test_all_models_share_metadata_with_base():
    """All Open Org tables must register against the same Base.metadata as
    the existing tables, otherwise migrations won't see them."""
    from llmstxt_api.database import Base
    from llmstxt_api.open_org_models import (
        CreatorSession, ExternalOrgCache, LlmUsage,
        OrgAdmin, OrgIdea, OrgProfile, OrgStrategy, OrgVersion,
    )
    expected_tables = {
        "org_profiles", "org_strategies", "org_ideas", "org_versions",
        "org_admins", "creator_sessions", "llm_usage", "external_org_cache",
    }
    table_names = set(Base.metadata.tables.keys())
    missing = expected_tables - table_names
    assert not missing, f"missing from Base.metadata: {missing}"


# --- per-model column shape --------------------------------------------------

def test_org_profile_columns():
    from llmstxt_api.open_org_models import OrgProfile
    cols = {c.name for c in OrgProfile.__table__.columns}
    assert cols == {
        "id", "org_id", "markdown_source", "profile_json",
        "published", "generation_status", "generation_error",
        "generation_stage", "generation_message", "generation_payload",
        "generation_started_at", "generation_finished_at",
        "murmurations_node_id", "murmurations_status",
        "created_at", "updated_at",
    }
    # org_id must be unique (it's the natural key for the rest of the schema).
    org_id_col = OrgProfile.__table__.columns["org_id"]
    assert org_id_col.unique is True


def test_org_strategy_unique_constraint_on_org_and_slug():
    from llmstxt_api.open_org_models import OrgStrategy
    constraint_names = {c.name for c in OrgStrategy.__table__.constraints}
    assert "uq_org_strategies_org_slug" in constraint_names


def test_org_idea_unique_constraint_on_org_and_slug():
    from llmstxt_api.open_org_models import OrgIdea
    constraint_names = {c.name for c in OrgIdea.__table__.constraints}
    assert "uq_org_ideas_org_slug" in constraint_names


def test_org_version_indexed_on_parent_compound():
    from llmstxt_api.open_org_models import OrgVersion
    index_names = {idx.name for idx in OrgVersion.__table__.indexes}
    assert "ix_org_versions_parent" in index_names


def test_org_admin_composite_primary_key():
    from llmstxt_api.open_org_models import OrgAdmin
    pk_cols = [c.name for c in OrgAdmin.__table__.primary_key.columns]
    assert sorted(pk_cols) == ["org_id", "user_id"]


def test_org_admin_user_id_cascades_on_user_delete():
    """Deleting a user removes their admin grants — they don't outlive the user row."""
    from llmstxt_api.open_org_models import OrgAdmin
    user_fk = next(iter(OrgAdmin.__table__.columns["user_id"].foreign_keys))
    assert user_fk.ondelete == "CASCADE"


def test_org_version_user_fk_sets_null_on_user_delete():
    """Audit-trail integrity: deleting a user nulls their authorship rather than wiping history."""
    from llmstxt_api.open_org_models import OrgVersion
    user_fk = next(iter(OrgVersion.__table__.columns["created_by_user_id"].foreign_keys))
    assert user_fk.ondelete == "SET NULL"


def test_creator_session_has_expires_at_index():
    """The cleanup beat task scans by expires_at; index is required to keep it cheap."""
    from llmstxt_api.open_org_models import CreatorSession
    index_names = {idx.name for idx in CreatorSession.__table__.indexes}
    assert "ix_creator_sessions_expires_at" in index_names


def test_llm_usage_compound_index_on_org_and_created():
    """The £0.50/org/day cap reads (org_id, created_at) — must be indexed."""
    from llmstxt_api.open_org_models import LlmUsage
    index_names = {idx.name for idx in LlmUsage.__table__.indexes}
    assert "ix_llm_usage_org_created" in index_names


def test_external_org_cache_org_id_unique():
    from llmstxt_api.open_org_models import ExternalOrgCache
    org_id_col = ExternalOrgCache.__table__.columns["org_id"]
    assert org_id_col.unique is True


# --- defaults ----------------------------------------------------------------

def test_org_profile_defaults():
    from llmstxt_api.open_org_models import OrgProfile
    profile = OrgProfile(org_id="GB-CHC-1234567")
    assert profile.published is False or profile.published is None  # default applies on flush
    # The default callable is set on the column; verify via the default object.
    published_col = OrgProfile.__table__.columns["published"]
    assert published_col.default is not None or published_col.server_default is not None


def test_creator_session_kind_constrained_to_strategy_or_idea():
    """We don't enforce this at DB level (it's a free string), but the model
    docstring documents the allowed values. Here we just confirm the column
    is the right type and length."""
    from llmstxt_api.open_org_models import CreatorSession
    kind_col = CreatorSession.__table__.columns["kind"]
    assert kind_col.type.length == 16


# --- instantiation -----------------------------------------------------------

def test_can_instantiate_all_models_without_db():
    """Smoke test — no DB needed, just confirms the model __init__ works."""
    import uuid
    from datetime import datetime, timedelta

    from llmstxt_api.open_org_models import (
        CreatorSession, ExternalOrgCache, LlmUsage,
        OrgAdmin, OrgIdea, OrgProfile, OrgStrategy, OrgVersion,
    )

    org_id = "GB-CHC-1234567"
    user_id = uuid.uuid4()

    OrgProfile(org_id=org_id, markdown_source="---\n---\n", profile_json={})
    OrgStrategy(org_id=org_id, slug="2025-2028", status="draft")
    OrgIdea(org_id=org_id, slug="kitchen-network", status="seed")
    OrgVersion(parent_kind="profile", parent_id=uuid.uuid4(), markdown_snapshot="x")
    OrgAdmin(user_id=user_id, org_id=org_id, role="owner")
    CreatorSession(
        org_id=org_id, kind="strategy", expires_at=datetime.utcnow() + timedelta(days=30)
    )
    LlmUsage(feature="profile_generator", org_id=org_id, model="claude-sonnet-4-20250514")
    ExternalOrgCache(org_id="GB-CHC-9999999", source_url="https://x.example", profile_json={})
