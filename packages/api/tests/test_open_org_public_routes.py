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


# --- listing strategies + ideas --------------------------------------------


def _execute_returning(session, scalars_value=None, scalar_value=None):
    """Wire ``session.execute`` to dispatch by call order.

    The list endpoints call execute twice: first for the profile published
    check (scalar_one_or_none), then for the rows query (scalars().all()).
    Tests can pass both shapes via ``side_effect``.
    """
    profile_result = mock.MagicMock()
    profile_result.scalar_one_or_none.return_value = scalar_value
    rows_result = mock.MagicMock()
    rows_result.scalars.return_value.all.return_value = scalars_value or []
    session.execute.side_effect = [profile_result, rows_result]


def test_list_strategies_returns_summaries_when_profile_published(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgStrategy

    strategies = [
        OrgStrategy(
            org_id="GB-CHC-1",
            slug="2025-2028",
            strategy_json={
                "summary": "Three-year plan to grow community kitchens across the borough."
            },
            themes=["food_access", "community_development"],
            status="active",
            published=True,
        ),
    ]
    _execute_returning(
        app_with_public_routes.state.mock_session,
        scalars_value=strategies,
        scalar_value=True,
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["slug"] == "2025-2028"
    assert body[0]["status"] == "active"
    assert "food_access" in body[0]["themes"]
    assert body[0]["summary"].startswith("Three-year plan")


def test_list_strategies_404_when_profile_unpublished(app_with_public_routes):
    _execute_returning(
        app_with_public_routes.state.mock_session,
        scalars_value=[],
        scalar_value=False,
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies")
    assert response.status_code == 404


def test_list_strategies_returns_empty_array_when_none_published(app_with_public_routes):
    _execute_returning(
        app_with_public_routes.state.mock_session,
        scalars_value=[],
        scalar_value=True,
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies")
    assert response.status_code == 200
    assert response.json() == []


def test_list_ideas_returns_summaries(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgIdea

    ideas = [
        OrgIdea(
            org_id="GB-CHC-1",
            slug="literacy-pop-up",
            idea_json={"summary": "Six-week intensive reading sessions in libraries."},
            themes=["education"],
            status="developing",
            published=True,
        ),
    ]
    _execute_returning(
        app_with_public_routes.state.mock_session,
        scalars_value=ideas,
        scalar_value=True,
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/ideas")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["slug"] == "literacy-pop-up"
    assert body[0]["status"] == "developing"
    assert body[0]["themes"] == ["education"]


def test_list_ideas_404_when_profile_unpublished(app_with_public_routes):
    _execute_returning(
        app_with_public_routes.state.mock_session,
        scalars_value=[],
        scalar_value=False,
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/ideas")
    assert response.status_code == 404
