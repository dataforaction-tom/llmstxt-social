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
    assert body["ideas_count"] == 3
