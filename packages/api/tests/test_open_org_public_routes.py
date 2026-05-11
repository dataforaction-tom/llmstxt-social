"""Tests for the public Open Org JSON serving routes (no auth)."""

import uuid
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_public_routes():
    """Build a minimal FastAPI app exposing only the public routes."""
    from llmstxt_api.database import get_db
    from llmstxt_api.routes.open_org_public import router

    app = FastAPI()
    app.include_router(router)

    session = mock.AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.state.mock_session = session
    return app


# --- profile.json -----------------------------------------------------------

def test_get_profile_json_returns_payload_when_published(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        profile_json={"identity": {"name": "Riverside"}, "mission": {"themes": ["loneliness"]}},
        published=True,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = profile
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/profile.json")
    assert response.status_code == 200
    body = response.json()
    assert body["identity"]["name"] == "Riverside"


def test_get_profile_json_returns_404_when_not_found(app_with_public_routes):
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = None
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-9999/profile.json")
    assert response.status_code == 404


def test_get_profile_json_returns_404_when_not_published(app_with_public_routes):
    """Unpublished profiles are private — return 404, not 403, to avoid leaking existence."""
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        profile_json={"identity": {"name": "Riverside"}},
        published=False,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = profile
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/profile.json")
    assert response.status_code == 404


def test_get_profile_json_sets_cache_control_header(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        org_id="GB-CHC-1234567",
        profile_json={"identity": {"name": "Riverside"}, "mission": {"themes": ["x"]}},
        published=True,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = profile
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/profile.json")
    cache_control = response.headers.get("cache-control", "")
    assert "public" in cache_control
    assert "max-age" in cache_control


# --- strategies/{slug}.json -------------------------------------------------

def test_get_strategy_json(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgStrategy

    strategy = OrgStrategy(
        org_id="GB-CHC-1234567",
        slug="2025-2028",
        strategy_json={"schema_version": "open-org-strategy/v0.1", "summary": "test"},
        published=True,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = strategy
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/strategies/2025-2028.json")
    assert response.status_code == 200
    assert response.json()["summary"] == "test"


def test_get_strategy_404_when_unpublished(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgStrategy

    strategy = OrgStrategy(
        org_id="GB-CHC-1234567",
        slug="2025-2028",
        strategy_json={"summary": "draft"},
        published=False,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = strategy
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/strategies/2025-2028.json")
    assert response.status_code == 404


# --- ideas/{slug}.json ------------------------------------------------------

def test_get_idea_json(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgIdea

    idea = OrgIdea(
        org_id="GB-CHC-1234567",
        slug="kitchen-network",
        idea_json={"schema_version": "open-org-idea/v0.1", "summary": "test"},
        published=True,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = idea
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/ideas/kitchen-network.json")
    assert response.status_code == 200


def test_get_idea_404_when_unpublished(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgIdea

    idea = OrgIdea(
        org_id="GB-CHC-1234567",
        slug="kitchen-network",
        idea_json={"summary": "draft"},
        published=False,
    )
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = idea
    app_with_public_routes.state.mock_session.execute.return_value = result

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1234567/ideas/kitchen-network.json")
    assert response.status_code == 404
