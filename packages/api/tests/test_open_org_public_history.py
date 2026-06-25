"""Tests for the public Open Org version-history routes (no auth).

Covers the three trajectory endpoints added for "profile evolution":

* ``GET /open-org/{org_id}/history``               — all profile+strategy+idea snapshots
* ``GET /open-org/{org_id}/strategies/{slug}/history`` — one strategy's snapshots
* ``GET /open-org/{org_id}/ideas/{slug}/history``      — one idea's snapshots

All three 404 for unpublished profiles so we don't leak existence. The
org-wide history endpoint sorts by ``created_at`` descending (most recent
first) and emits a human-readable ``summary`` per snapshot.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_public_routes():
    """Minimal FastAPI app exposing only the public routes."""
    from llmstxt_api.database import get_db
    from llmstxt_api.routes.open_org_public import router

    app = FastAPI()
    app.include_router(router)

    session = mock.AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.state.mock_session = session
    return app


def _scalar_result(value):
    r = mock.MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values):
    r = mock.MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


# --- /history (org-wide) ----------------------------------------------------


def test_org_history_404_when_profile_unpublished(app_with_public_routes):
    """Unpublished profiles must not expose history — 404, not 403."""
    app_with_public_routes.state.mock_session.execute.return_value = _scalar_result(
        False
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/history")
    assert response.status_code == 404


def test_org_history_returns_version_list_for_published_profile(
    app_with_public_routes,
):
    from llmstxt_api.open_org_models import OrgProfile, OrgStrategy, OrgVersion

    profile_id = uuid.uuid4()
    strategy_id = uuid.uuid4()
    base = datetime(2026, 5, 10, 12, 0, 0)

    profile = OrgProfile(
        id=profile_id, org_id="GB-CHC-1", published=True
    )
    strategy = OrgStrategy(
        id=strategy_id, org_id="GB-CHC-1", slug="2025-2028", published=True
    )

    versions = [
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="profile",
            parent_id=profile_id,
            markdown_snapshot="## Mission\nProfile generated from charity number 1234567.",
            created_at=base,
        ),
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="strategy",
            parent_id=strategy_id,
            markdown_snapshot="## Summary\nThree-year plan to grow community kitchens.",
            created_at=base + timedelta(days=30),
        ),
    ]

    # execute calls: 1) profile published check, 2) strategies for slug map,
    #   3) ideas for slug map, 4) versions query
    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalars_result([strategy]),
        _scalars_result([]),
        _scalars_result(versions),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/history")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    # strategy version is newer → appears first (descending sort)
    assert body[0]["parent_kind"] == "strategy"
    assert body[0]["parent_slug"] == "2025-2028"
    assert body[1]["parent_kind"] == "profile"
    assert body[1]["parent_slug"] is None
    # summaries are extracted from the snapshot body
    assert "1234567" in body[1]["summary"]
    assert "Three-year plan" in body[0]["summary"]


def test_org_history_sorts_most_recent_first(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgProfile, OrgVersion

    profile_id = uuid.uuid4()
    profile = OrgProfile(id=profile_id, org_id="GB-CHC-1", published=True)

    # Versions deliberately out of order in the fake result set — the endpoint
    # must sort by created_at descending regardless of DB row order.
    oldest = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile_id,
        markdown_snapshot="oldest",
        created_at=datetime(2026, 1, 1),
    )
    newest = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile_id,
        markdown_snapshot="newest",
        created_at=datetime(2026, 6, 1),
    )
    middle = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile_id,
        markdown_snapshot="middle",
        created_at=datetime(2026, 3, 1),
    )

    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalars_result([]),  # strategies for slug map
        _scalars_result([]),  # ideas for slug map
        _scalars_result([oldest, newest, middle]),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/history")
    assert response.status_code == 200
    body = response.json()
    assert [e["summary"] for e in body] == ["newest", "middle", "oldest"]


def test_org_history_empty_when_no_versions(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(id=uuid.uuid4(), org_id="GB-CHC-1", published=True)

    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalars_result([]),  # strategies
        _scalars_result([]),  # ideas
        _scalars_result([]),  # versions
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/history")
    assert response.status_code == 200
    assert response.json() == []


# --- /strategies/{slug}/history --------------------------------------------


def test_strategy_history_404_when_profile_unpublished(app_with_public_routes):
    app_with_public_routes.state.mock_session.execute.return_value = _scalar_result(
        False
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies/2025-2028/history")
    assert response.status_code == 404


def test_strategy_history_404_when_strategy_not_found(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgProfile

    # profile published check, then strategy lookup → None
    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalar_result(None),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies/missing/history")
    assert response.status_code == 404


def test_strategy_history_returns_versions_for_published_strategy(
    app_with_public_routes,
):
    from llmstxt_api.open_org_models import OrgStrategy, OrgVersion

    strategy_id = uuid.uuid4()
    strategy = OrgStrategy(
        id=strategy_id, org_id="GB-CHC-1", slug="2025-2028", published=True
    )
    versions = [
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="strategy",
            parent_id=strategy_id,
            markdown_snapshot="## Summary\nDraft plan.",
            created_at=datetime(2026, 5, 1),
        ),
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="strategy",
            parent_id=strategy_id,
            markdown_snapshot="## Summary\nFinal plan with detail.",
            created_at=datetime(2026, 6, 1),
        ),
    ]

    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalar_result(strategy),
        _scalars_result(versions),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies/2025-2028/history")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["summary"].startswith("Final plan")
    assert body[1]["summary"].startswith("Draft plan")
    assert all(e["parent_kind"] == "strategy" for e in body)
    assert all(e["parent_slug"] == "2025-2028" for e in body)


def test_strategy_history_404_when_strategy_unpublished(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgStrategy

    strategy = OrgStrategy(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        slug="2025-2028",
        published=False,
    )
    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalar_result(strategy),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/strategies/2025-2028/history")
    assert response.status_code == 404


# --- /ideas/{slug}/history --------------------------------------------------


def test_idea_history_404_when_profile_unpublished(app_with_public_routes):
    app_with_public_routes.state.mock_session.execute.return_value = _scalar_result(
        False
    )

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/ideas/kitchen/history")
    assert response.status_code == 404


def test_idea_history_returns_versions_for_published_idea(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgIdea, OrgVersion

    idea_id = uuid.uuid4()
    idea = OrgIdea(
        id=idea_id, org_id="GB-CHC-1", slug="kitchen", published=True
    )
    versions = [
        OrgVersion(
            id=uuid.uuid4(),
            parent_kind="idea",
            parent_id=idea_id,
            markdown_snapshot="## Summary\nSeed idea for a community kitchen.",
            created_at=datetime(2026, 5, 1),
        ),
    ]

    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalar_result(idea),
        _scalars_result(versions),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/ideas/kitchen/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["parent_kind"] == "idea"
    assert body[0]["parent_slug"] == "kitchen"
    assert "Seed idea" in body[0]["summary"]


def test_idea_history_404_when_idea_unpublished(app_with_public_routes):
    from llmstxt_api.open_org_models import OrgIdea

    idea = OrgIdea(
        id=uuid.uuid4(), org_id="GB-CHC-1", slug="kitchen", published=False
    )
    app_with_public_routes.state.mock_session.execute.side_effect = [
        _scalar_result(True),
        _scalar_result(idea),
    ]

    client = TestClient(app_with_public_routes)
    response = client.get("/open-org/GB-CHC-1/ideas/kitchen/history")
    assert response.status_code == 404