"""Tests for funder signalling routes (Phase 1 — public, no auth).

Signals let funders express interest in a published idea. Phase 1 is
transparent: signals are publicly visible. All body fields are optional so a
funder can signal anonymously.
"""

import uuid
from datetime import datetime
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_signal_routes():
    """Build a minimal FastAPI app exposing only the signal routes under /api."""
    from llmstxt_api.database import get_db
    from llmstxt_api.routes.open_org_signals import router

    app = FastAPI()
    # The router carries its own /api/open-org prefix.
    app.include_router(router)

    session = mock.AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.state.mock_session = session
    return app


def _make_idea(org_id="GB-CHC-1", slug="kitchen-network", published=True):
    from llmstxt_api.open_org_models import OrgIdea

    return OrgIdea(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        idea_json={"summary": "test"},
        published=published,
    )


def _make_profile(org_id="GB-CHC-1", published=True):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        profile_json={"identity": {"name": "Riverside"}},
        published=published,
    )


def _make_signal(**kwargs):
    from llmstxt_api.open_org_models import OrgSignal

    defaults = dict(
        id=uuid.uuid4(),
        idea_id=uuid.uuid4(),
        org_id="GB-CHC-1",
        signal_type="interest",
        funder_name=None,
        funder_email=None,
        message=None,
        created_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return OrgSignal(**defaults)


def _profile_result(profile):
    """Mock result for ``select(OrgProfile.published)`` → scalar_one_or_none.

    The query selects only the ``published`` column, so the scalar is a
    boolean (or None when the profile row doesn't exist).
    """
    r = mock.MagicMock()
    if profile is None:
        r.scalar_one_or_none.return_value = None
    else:
        r.scalar_one_or_none.return_value = profile.published
    return r


def _idea_result(idea):
    """Mock result for ``select(OrgIdea)`` → scalar_one_or_none."""
    r = mock.MagicMock()
    r.scalar_one_or_none.return_value = idea
    return r


def _list_result(items):
    """Mock result for ``select(OrgSignal)`` → scalars().all()."""
    r = mock.MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


# --- POST /ideas/{org_id}/{slug}/signal -------------------------------------

def test_post_signal_on_published_idea_returns_201(app_with_signal_routes):
    idea = _make_idea()
    profile = _make_profile()
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post(
        "/api/open-org/ideas/GB-CHC-1/kitchen-network/signal",
        json={"funder_name": "ACME Foundation", "message": "Interested!"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["org_id"] == "GB-CHC-1"
    assert body["signal_type"] == "interest"
    assert body["funder_name"] == "ACME Foundation"
    assert body["message"] == "Interested!"
    app_with_signal_routes.state.mock_session.add.assert_called_once()
    app_with_signal_routes.state.mock_session.commit.assert_awaited_once()


def test_post_signal_on_unpublished_idea_returns_404(app_with_signal_routes):
    profile = _make_profile()
    idea = _make_idea(published=False)
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post(
        "/api/open-org/ideas/GB-CHC-1/kitchen-network/signal",
        json={},
    )
    assert response.status_code == 404


def test_post_signal_on_unpublished_profile_returns_404(app_with_signal_routes):
    profile = _make_profile(published=False)
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post(
        "/api/open-org/ideas/GB-CHC-1/kitchen-network/signal",
        json={},
    )
    assert response.status_code == 404


def test_post_signal_on_non_existent_idea_returns_404(app_with_signal_routes):
    profile = _make_profile()
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(None),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post(
        "/api/open-org/ideas/GB-CHC-1/no-such-idea/signal",
        json={},
    )
    assert response.status_code == 404


def test_post_signal_with_message_stored_correctly(app_with_signal_routes):
    idea = _make_idea()
    profile = _make_profile()

    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post(
        "/api/open-org/ideas/GB-CHC-1/kitchen-network/signal",
        json={"funder_name": "Beta", "funder_email": "beta@example.org", "message": "Keen"},
    )
    assert response.status_code == 201
    # The OrgSignal passed to session.add carries the submitted fields.
    add_calls = app_with_signal_routes.state.mock_session.add.call_args_list
    assert len(add_calls) == 1
    obj = add_calls[0].args[0]
    assert obj.message == "Keen"
    assert obj.funder_email == "beta@example.org"
    assert obj.signal_type == "interest"
    assert str(obj.idea_id) == str(idea.id)


def test_post_signal_with_no_body_returns_201(app_with_signal_routes):
    idea = _make_idea()
    profile = _make_profile()
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.post("/api/open-org/ideas/GB-CHC-1/kitchen-network/signal")
    assert response.status_code == 201
    body = response.json()
    assert body["funder_name"] is None
    assert body["funder_email"] is None
    assert body["message"] is None


# --- GET /ideas/{org_id}/{slug}/signals ------------------------------------

def test_get_signals_for_published_idea_returns_list(app_with_signal_routes):
    profile = _make_profile()
    idea = _make_idea()
    signals = [
        _make_signal(funder_name="Funder A", message="Hi"),
        _make_signal(funder_name="Funder B"),
    ]
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
        _list_result(signals),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.get("/api/open-org/ideas/GB-CHC-1/kitchen-network/signals")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["funder_name"] == "Funder A"


def test_get_signals_for_unpublished_idea_returns_404(app_with_signal_routes):
    profile = _make_profile()
    idea = _make_idea(published=False)
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _idea_result(idea),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.get("/api/open-org/ideas/GB-CHC-1/kitchen-network/signals")
    assert response.status_code == 404


def test_get_signals_for_unpublished_profile_returns_404(app_with_signal_routes):
    profile = _make_profile(published=False)
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.get("/api/open-org/ideas/GB-CHC-1/kitchen-network/signals")
    assert response.status_code == 404


# --- GET /{org_id}/signals ------------------------------------------------

def test_get_org_signals_returns_aggregated_list(app_with_signal_routes):
    profile = _make_profile()
    signals = [
        _make_signal(funder_name="A"),
        _make_signal(funder_name="B"),
    ]
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
        _list_result(signals),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.get("/api/open-org/GB-CHC-1/signals")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2


def test_get_org_signals_404_when_profile_unpublished(app_with_signal_routes):
    profile = _make_profile(published=False)
    app_with_signal_routes.state.mock_session.execute.side_effect = [
        _profile_result(profile),
    ]

    client = TestClient(app_with_signal_routes)
    response = client.get("/api/open-org/GB-CHC-1/signals")
    assert response.status_code == 404