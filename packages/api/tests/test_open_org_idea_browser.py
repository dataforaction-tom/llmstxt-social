"""Tests for the public GET /api/open-org/discover/ideas route.

Cross-org idea listing. Joins OrgIdea against its parent OrgProfile so
unpublished profiles don't leak orphan ideas. Tests stub the DB at the
session.execute level.
"""

from __future__ import annotations

import uuid
from unittest import mock


def _idea(*, org_id: str, slug: str, themes: list[str] | None = None,
          status: str = "developing", summary: str | None = None,
          cost_lower: int | None = None, cost_upper: int | None = None):
    from llmstxt_api.open_org_models import OrgIdea

    idea_json = {
        "schema_version": "open-org-idea/v0.1",
        "id": slug,
        "status": status,
        "themes": themes or ["education"],
    }
    if summary:
        idea_json["summary"] = summary
    if cost_lower is not None or cost_upper is not None:
        idea_json["indicative_cost"] = {
            "lower": cost_lower,
            "upper": cost_upper,
            "currency": "GBP",
        }

    return OrgIdea(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        published=True,
        themes=themes or ["education"],
        status=status,
        idea_json=idea_json,
    )


def _profile(*, org_id: str, name: str, area: str | None = None):
    from llmstxt_api.open_org_models import OrgProfile

    geography: dict = {}
    if area:
        geography["primary_area"] = area
    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        published=True,
        profile_json={
            "identity": {"name": name, "geography": geography} if geography else {"identity": {"name": name}},
        },
    )


def _stub_db(*, ideas: list, profiles: list):
    """AsyncSession whose execute() returns ideas then profiles."""
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    db.execute.side_effect = [_wrap(ideas), _wrap(profiles)]
    return db


async def test_idea_browser_returns_ideas_with_org_name():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    profile = _profile(org_id="GB-CHC-1", name="Riverside Trust", area="Great Yarmouth")
    # Patch profile_json so name is at identity.name (the helper above has a
    # quirk where geography alone keeps the right shape).
    profile.profile_json = {
        "identity": {"name": "Riverside Trust", "geography": {"primary_area": "Great Yarmouth"}},
    }
    db = _stub_db(
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="kitchen-network",
                themes=["food_access"],
                summary="Three community kitchens.",
                cost_lower=80_000,
                cost_upper=120_000,
            ),
        ],
        profiles=[profile],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    assert len(body["results"]) == 1
    row = body["results"][0]
    assert row["org_id"] == "GB-CHC-1"
    assert row["org_name"] == "Riverside Trust"
    assert row["slug"] == "kitchen-network"
    assert row["themes"] == ["food_access"]
    assert row["cost_lower"] == 80_000
    assert row["primary_area"] == "Great Yarmouth"
    assert row["profile_url"] == "/openorg/GB-CHC-1"
    assert row["idea_url"] == "/open-org/GB-CHC-1/ideas/kitchen-network.json"


async def test_idea_browser_excludes_ideas_whose_parent_profile_unpublished():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    # The query already filters profiles to published=True, so the orphan
    # idea simply doesn't get a matching profile row.
    db = _stub_db(
        ideas=[_idea(org_id="GB-CHC-1", slug="orphan")],
        profiles=[],  # parent profile not in the published list
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    assert body["results"] == []


async def test_idea_browser_filters_by_cost_max():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    profile = _profile(org_id="GB-CHC-1", name="X")
    profile.profile_json = {"identity": {"name": "X"}}

    db = _stub_db(
        ideas=[
            _idea(org_id="GB-CHC-1", slug="cheap", cost_lower=5_000),
            _idea(org_id="GB-CHC-1", slug="dear", cost_lower=200_000),
        ],
        profiles=[profile],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=50_000, cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == ["cheap"]


async def test_idea_browser_free_text_search():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    db = _stub_db(
        ideas=[
            _idea(org_id="GB-CHC-1", slug="kitchen", summary="Community kitchens"),
            _idea(org_id="GB-CHC-1", slug="literacy", summary="Reading sessions"),
        ],
        profiles=[profile],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q="kitchen",
        cost_max=None, cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == ["kitchen"]


async def test_idea_browser_paginates_by_cursor():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    profile_a = _profile(org_id="GB-CHC-A", name="Alpha")
    profile_a.profile_json = {"identity": {"name": "Alpha"}}
    profile_b = _profile(org_id="GB-CHC-B", name="Beta")
    profile_b.profile_json = {"identity": {"name": "Beta"}}

    db = _stub_db(
        ideas=[
            _idea(org_id="GB-CHC-A", slug="one"),
            _idea(org_id="GB-CHC-A", slug="two"),
            _idea(org_id="GB-CHC-B", slug="three"),
        ],
        profiles=[profile_a, profile_b],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, cursor=None, limit=2, db=db,
    )
    import json
    body = json.loads(response.body)
    assert len(body["results"]) == 2
    assert body["next_cursor"] is not None


async def test_idea_browser_returns_empty_when_no_ideas():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalars=mock.MagicMock(
            return_value=mock.MagicMock(all=mock.MagicMock(return_value=[]))
        )
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    assert body["results"] == []
    assert body["next_cursor"] is None
