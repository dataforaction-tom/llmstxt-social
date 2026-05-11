"""Tests for the admin edit routes (profile/strategy/idea markdown CRUD)."""

import uuid
from datetime import datetime
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# --- worked markdown samples ------------------------------------------------

VALID_PROFILE_MD = """---
schema_version: open-org/v0.1
identity:
  name: "Test Trust"
  registration:
    charity_commission_ew: "1234567"
  geography:
    primary_area: "Manchester"
mission:
  themes:
    - older_people
    - loneliness
---

## Mission

We do good work for older people in Manchester.
"""


VALID_STRATEGY_MD = """---
schema_version: open-org-strategy/v0.1
id: "2025-2028"
status: draft
themes:
  - older_people
---

## Summary

Three-year plan.
"""


VALID_IDEA_MD = """---
schema_version: open-org-idea/v0.1
id: "test-idea"
status: seed
themes:
  - food_access
---

## Summary

Test idea.
"""


# --- fixtures ---------------------------------------------------------------

@pytest.fixture
def app_with_admin_routes():
    from llmstxt_api.database import get_db
    from llmstxt_api.routes.open_org_admin import router
    from llmstxt_api.routes.open_org_auth import require_org_admin

    app = FastAPI()
    app.include_router(router)

    session = mock.AsyncMock()
    app.dependency_overrides[get_db] = lambda: session

    # Auto-authorise — individual tests can override per-org if needed.
    fake_admin = mock.MagicMock()
    fake_admin.user_id = uuid.uuid4()
    fake_admin.role = "owner"
    app.dependency_overrides[require_org_admin] = lambda: fake_admin

    app.state.mock_session = session
    app.state.fake_admin = fake_admin
    return app


def _mock_execute_returning(session, value):
    """Wire session.execute() to return a result whose scalar_one_or_none gives ``value``."""
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute.return_value = result


# --- profile.md GET ---------------------------------------------------------

def test_get_profile_md_returns_markdown_source(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        markdown_source=VALID_PROFILE_MD,
        profile_json={},
        published=False,
    )
    _mock_execute_returning(app_with_admin_routes.state.mock_session, profile)

    client = TestClient(app_with_admin_routes)
    response = client.get("/api/open-org/GB-CHC-1/profile.md")
    assert response.status_code == 200
    assert response.json()["markdown"] == VALID_PROFILE_MD


def test_get_profile_md_returns_404_when_no_profile(app_with_admin_routes):
    _mock_execute_returning(app_with_admin_routes.state.mock_session, None)

    client = TestClient(app_with_admin_routes)
    response = client.get("/api/open-org/GB-CHC-1/profile.md")
    assert response.status_code == 404


# --- profile.md PUT ---------------------------------------------------------

def test_put_profile_md_validates_and_saves(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile

    existing = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        markdown_source="(old)",
        profile_json={},
    )
    _mock_execute_returning(app_with_admin_routes.state.mock_session, existing)

    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-1/profile.md",
        json={"markdown": VALID_PROFILE_MD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["saved"] is True
    # The PUT must update the in-memory row AND derive the JSON.
    assert existing.markdown_source == VALID_PROFILE_MD
    assert existing.profile_json["identity"]["name"] == "Test Trust"


def test_put_profile_md_rejects_invalid_markdown_with_400(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile

    existing = OrgProfile(id=uuid.uuid4(), org_id="GB-CHC-1", markdown_source="(old)")
    _mock_execute_returning(app_with_admin_routes.state.mock_session, existing)

    incomplete = "---\nschema_version: open-org/v0.1\n---\n## Mission\nNo identity.\n"
    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-1/profile.md",
        json={"markdown": incomplete},
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body or "errors" in body


def test_put_profile_md_snapshots_to_org_versions(app_with_admin_routes):
    """On every save, the previous markdown is preserved in org_versions."""
    from llmstxt_api.open_org_models import OrgProfile, OrgVersion

    existing = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        markdown_source="(old)",
        profile_json={},
    )
    session = app_with_admin_routes.state.mock_session
    _mock_execute_returning(session, existing)

    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-1/profile.md",
        json={"markdown": VALID_PROFILE_MD},
    )
    assert response.status_code == 200

    # session.add was called at least once with an OrgVersion
    added_versions = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], OrgVersion)
    ]
    assert added_versions, "expected an OrgVersion snapshot to be added"
    version = added_versions[0]
    assert version.parent_kind == "profile"
    assert version.parent_id == existing.id
    assert version.markdown_snapshot == VALID_PROFILE_MD


def test_put_profile_md_creates_profile_when_none_exists(app_with_admin_routes):
    """First-time save creates the OrgProfile row (e.g. before profile generator runs)."""
    _mock_execute_returning(app_with_admin_routes.state.mock_session, None)

    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-new/profile.md",
        json={"markdown": VALID_PROFILE_MD},
    )
    # Allowing 200 or 201 — implementation choice. Just shouldn't be 404.
    assert response.status_code in (200, 201)


# --- strategy CRUD ----------------------------------------------------------

def test_get_strategy_md(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgStrategy

    strategy = OrgStrategy(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        slug="2025-2028",
        markdown_source=VALID_STRATEGY_MD,
        strategy_json={},
    )
    _mock_execute_returning(app_with_admin_routes.state.mock_session, strategy)

    client = TestClient(app_with_admin_routes)
    response = client.get("/api/open-org/GB-CHC-1/strategies/2025-2028.md")
    assert response.status_code == 200
    assert response.json()["markdown"] == VALID_STRATEGY_MD


def test_put_strategy_md_creates_when_missing(app_with_admin_routes):
    _mock_execute_returning(app_with_admin_routes.state.mock_session, None)

    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-1/strategies/2025-2028.md",
        json={"markdown": VALID_STRATEGY_MD},
    )
    assert response.status_code in (200, 201)


# --- idea CRUD --------------------------------------------------------------

def test_get_idea_md(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgIdea

    idea = OrgIdea(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        slug="test-idea",
        markdown_source=VALID_IDEA_MD,
        idea_json={},
    )
    _mock_execute_returning(app_with_admin_routes.state.mock_session, idea)

    client = TestClient(app_with_admin_routes)
    response = client.get("/api/open-org/GB-CHC-1/ideas/test-idea.md")
    assert response.status_code == 200


def test_put_idea_md_validates_and_saves(app_with_admin_routes):
    _mock_execute_returning(app_with_admin_routes.state.mock_session, None)

    client = TestClient(app_with_admin_routes)
    response = client.put(
        "/api/open-org/GB-CHC-1/ideas/test-idea.md",
        json={"markdown": VALID_IDEA_MD},
    )
    assert response.status_code in (200, 201)


# --- history ---------------------------------------------------------------

def test_get_history_lists_versions_for_org(app_with_admin_routes):
    """Returns versions in reverse chronological order across all kinds."""
    from llmstxt_api.open_org_models import OrgVersion

    now = datetime.utcnow()
    parent_id = uuid.uuid4()
    versions = [
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="profile",
            parent_id=parent_id,
            markdown_snapshot="(v2)",
            created_at=now,
        ),
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="profile",
            parent_id=parent_id,
            markdown_snapshot="(v1)",
            created_at=now,
        ),
    ]
    session = app_with_admin_routes.state.mock_session

    # The handler does TWO queries: profile lookup (to scope by org), then
    # version list. Different return types from each call to .execute.
    profile_result = mock.MagicMock()
    profile_mock = mock.MagicMock()
    profile_mock.id = parent_id
    profile_result.scalar_one_or_none.return_value = profile_mock

    versions_result = mock.MagicMock()
    versions_result.scalars.return_value.all.return_value = versions
    session.execute.side_effect = [profile_result, versions_result]

    client = TestClient(app_with_admin_routes)
    response = client.get("/api/open-org/GB-CHC-1/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body["versions"]) == 2
    assert body["versions"][0]["parent_kind"] == "profile"
