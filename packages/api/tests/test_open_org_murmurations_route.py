"""Tests for the public Murmurations envelope route.

GET /open-org/{org_id}/murmurations.json returns the flat envelope the index
fetches and validates. 404 when unpublished (no existence leak).
"""

from __future__ import annotations

import json
import uuid
from unittest import mock

import pytest


def _profile(*, published: bool, profile_json: dict | None = None):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        published=published,
        profile_json=profile_json
        or {
            "schema_version": "open-org/v0.1",
            "identity": {
                "name": "Acme Aid",
                "identifiers": {"org_id": "GB-CHC-1234567"},
            },
            "mission": {"themes": ["education"]},
        },
    )


def _db_returning(*results):
    """Build an async session whose .execute() returns rows one call at a time."""
    db = mock.AsyncMock()
    db.execute.side_effect = [
        mock.MagicMock(scalar_one_or_none=mock.MagicMock(return_value=r))
        if not isinstance(r, list)
        else mock.MagicMock(scalars=mock.MagicMock(
            return_value=mock.MagicMock(all=mock.MagicMock(return_value=r))
        ))
        for r in results
    ]
    return db


async def test_returns_404_when_profile_does_not_exist():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_murmurations_envelope,
    )

    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc:
        await get_murmurations_envelope("GB-CHC-NONE", db)
    assert exc.value.status_code == 404


async def test_returns_404_when_profile_unpublished():
    """Unpublished profiles must 404, not leak existence via a different code."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_murmurations_envelope,
    )

    db = _db_returning(_profile(published=False))
    with pytest.raises(HTTPException) as exc:
        await get_murmurations_envelope("GB-CHC-1234567", db)
    assert exc.value.status_code == 404


async def test_returns_envelope_for_published_profile():
    from llmstxt_api.routes.open_org_public_murmurations import (
        get_murmurations_envelope,
    )

    profile = _profile(published=True)
    # Two extra queries: strategies (returns empty list) and ideas (empty list).
    db = _db_returning(profile, [], [])

    response = await get_murmurations_envelope("GB-CHC-1234567", db)

    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body["org_id_guide"] == "GB-CHC-1234567"
    assert body["name"] == "Acme Aid"
    assert body["linked_schemas"] == ["open_org_profile-v0.1.0"]


async def test_includes_strategy_themes_and_ideas_count_from_db():
    from llmstxt_api.open_org_models import OrgIdea, OrgStrategy
    from llmstxt_api.routes.open_org_public_murmurations import (
        get_murmurations_envelope,
    )

    profile = _profile(published=True)
    strategies = [
        OrgStrategy(
            org_id="GB-CHC-1234567",
            slug="s1",
            published=True,
            themes=["food_access", "community_development"],
        ),
        OrgStrategy(
            org_id="GB-CHC-1234567",
            slug="s2",
            published=True,
            themes=["food_access", "volunteering"],
        ),
    ]
    ideas = [
        OrgIdea(org_id="GB-CHC-1234567", slug="i1", published=True),
        OrgIdea(org_id="GB-CHC-1234567", slug="i2", published=True),
        OrgIdea(org_id="GB-CHC-1234567", slug="i3", published=True),
    ]
    db = _db_returning(profile, strategies, ideas)

    response = await get_murmurations_envelope("GB-CHC-1234567", db)

    body = json.loads(response.body)
    # Themes deduped across all published strategies.
    assert set(body["strategy_themes"]) == {
        "food_access",
        "community_development",
        "volunteering",
    }


# ---------------------------------------------------------------------------
# Per-record strategy Murmurations envelope
# ---------------------------------------------------------------------------


def _strategy(*, published: bool, strategy_json: dict | None = None):
    from llmstxt_api.open_org_models import OrgStrategy

    return OrgStrategy(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        slug="food-access-2024",
        published=published,
        strategy_json=strategy_json
        or {
            "id": "food-access-2024",
            "summary": "Expand food access programmes",
            "status": "active",
            "themes": ["food_access", "health"],
            "period": {"start": "2024-01-01", "end": "2026-12-31", "horizon": "3-year"},
        },
    )


def _db_returning_one(result):
    """Build an async session whose .execute() returns a single result."""
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=result)
    )
    return db


async def test_strategy_murmurations_returns_envelope():
    from llmstxt_api.routes.open_org_public_murmurations import (
        get_strategy_murmurations_envelope,
    )

    strategy = _strategy(published=True)
    db = _db_returning_one(strategy)

    with mock.patch("llmstxt_api.routes.open_org_public_murmurations.settings") as s:
        s.frontend_url = "https://openorg.good-ship.co.uk"
        response = await get_strategy_murmurations_envelope(
            "GB-CHC-1234567", "food-access-2024", db
        )

    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body["linked_schemas"] == ["open_org_strategy-v0.1.0"]
    assert body["org_id_guide"] == "GB-CHC-1234567"
    assert body["strategy_slug"] == "food-access-2024"
    assert body["name"] == "Expand food access programmes"
    assert body["status"] == "active"
    assert set(body["tags"]) == {"food_access", "health"}
    assert body["period_start"] == "2024-01-01"
    assert body["period_end"] == "2026-12-31"
    assert "open_org_strategy_url" in body


async def test_strategy_murmurations_404_when_unpublished():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_strategy_murmurations_envelope,
    )

    # The query filters on published=True, so an unpublished strategy
    # means the DB returns None.
    db = _db_returning_one(None)

    with pytest.raises(HTTPException) as exc:
        await get_strategy_murmurations_envelope(
            "GB-CHC-1234567", "food-access-2024", db
        )
    assert exc.value.status_code == 404


async def test_strategy_murmurations_404_when_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_strategy_murmurations_envelope,
    )

    db = _db_returning_one(None)

    with pytest.raises(HTTPException) as exc:
        await get_strategy_murmurations_envelope(
            "GB-CHC-1234567", "nonexistent", db
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Per-record idea Murmurations envelope
# ---------------------------------------------------------------------------


def _idea(*, published: bool, idea_json: dict | None = None):
    from llmstxt_api.open_org_models import OrgIdea

    return OrgIdea(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        slug="community-kitchen",
        published=published,
        idea_json=idea_json
        or {
            "id": "community-kitchen",
            "summary": "Weekly community kitchen",
            "status": "exploring",
            "themes": ["food_access", "community_development"],
            "place": {"description": "Great Yarmouth", "geolocation": {"lat": 52.6, "lon": 1.7}},
            "cost_range": {"min": 5000, "max": 15000, "currency": "GBP"},
        },
    )


async def test_idea_murmurations_returns_envelope():
    from llmstxt_api.routes.open_org_public_murmurations import (
        get_idea_murmurations_envelope,
    )

    idea = _idea(published=True)
    db = _db_returning_one(idea)

    with mock.patch("llmstxt_api.routes.open_org_public_murmurations.settings") as s:
        s.frontend_url = "https://openorg.good-ship.co.uk"
        response = await get_idea_murmurations_envelope(
            "GB-CHC-1234567", "community-kitchen", db
        )

    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body["linked_schemas"] == ["open_org_idea-v0.1.0"]
    assert body["org_id_guide"] == "GB-CHC-1234567"
    assert body["idea_slug"] == "community-kitchen"
    assert body["name"] == "Weekly community kitchen"
    assert body["status"] == "exploring"
    assert set(body["tags"]) == {"food_access", "community_development"}
    assert body["primary_area"] == "Great Yarmouth"
    assert body["geolocation"] == {"lat": 52.6, "lon": 1.7}
    assert body["cost_min"] == 5000
    assert body["cost_max"] == 15000
    assert body["cost_currency"] == "GBP"
    assert "open_org_idea_url" in body


async def test_idea_murmurations_404_when_unpublished():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_idea_murmurations_envelope,
    )

    # The query filters on published=True, so an unpublished idea
    # means the DB returns None.
    db = _db_returning_one(None)

    with pytest.raises(HTTPException) as exc:
        await get_idea_murmurations_envelope(
            "GB-CHC-1234567", "community-kitchen", db
        )
    assert exc.value.status_code == 404


async def test_idea_murmurations_404_when_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_public_murmurations import (
        get_idea_murmurations_envelope,
    )

    db = _db_returning_one(None)

    with pytest.raises(HTTPException) as exc:
        await get_idea_murmurations_envelope(
            "GB-CHC-1234567", "nonexistent", db
        )
    assert exc.value.status_code == 404
