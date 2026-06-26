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
    """AsyncSession whose execute() returns ideas, profiles, then signal counts.

    The discover_ideas handler now issues a third query — a GROUP BY over
    org_signals — so the stub must provide a third result (an empty list of
    (idea_id, count) tuples by default).
    """
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    # Third call is the signal-count aggregate — uses .all() directly.
    sig_result = mock.MagicMock()
    sig_result.all.return_value = []

    db.execute.side_effect = [_wrap(ideas), _wrap(profiles), sig_result]
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
        cost_max=None, sort="recent", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    assert body["results"] == []
    assert body["next_cursor"] is None


# --------------------------------------------------------------------------- #
# sort parameter — recent (default) | signals | status
# --------------------------------------------------------------------------- #


def _stub_db_with_signals(*, ideas: list, profiles: list, signal_rows: list):
    """AsyncSession whose execute() returns ideas, profiles, then signal counts.

    signal_rows is a list of (idea_id, count) tuples — the shape returned by
    the GROUP BY aggregate query.
    """
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    # Third call is the signal-count aggregate — it uses .all() directly on the
    # result, not .scalars().all().
    sig_result = mock.MagicMock()
    sig_result.all.return_value = signal_rows

    db.execute.side_effect = [_wrap(ideas), _wrap(profiles), sig_result]
    return db


async def test_sort_signals_returns_ideas_with_most_signals_first():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    idea_low = _idea(org_id="GB-CHC-1", slug="low-interest", themes=["education"])
    idea_high = _idea(org_id="GB-CHC-1", slug="high-interest", themes=["education"])
    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    # high-interest has 3 signals, low-interest has 1.
    signal_rows = [(idea_high.id, 3), (idea_low.id, 1)]

    db = _stub_db_with_signals(
        ideas=[idea_low, idea_high],
        profiles=[profile],
        signal_rows=signal_rows,
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, sort="signals", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == ["high-interest", "low-interest"]
    assert body["results"][0]["signal_count"] == 3
    assert body["results"][1]["signal_count"] == 1


async def test_sort_signals_falls_back_to_alphabetical_for_ties():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    idea_b = _idea(org_id="GB-CHC-1", slug="bbb", themes=["education"])
    idea_a = _idea(org_id="GB-CHC-1", slug="aaa", themes=["education"])
    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    # Both have 2 signals — tiebreak is alphabetical (aaa before bbb).
    signal_rows = [(idea_a.id, 2), (idea_b.id, 2)]

    db = _stub_db_with_signals(
        ideas=[idea_b, idea_a],
        profiles=[profile],
        signal_rows=signal_rows,
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, sort="signals", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == ["aaa", "bbb"]


async def test_sort_status_orders_by_maturity_seed_to_delivered():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    # Deliberately out of maturity order in the input list.
    idea_delivered = _idea(org_id="GB-CHC-1", slug="delivered-idea", status="delivered")
    idea_seed = _idea(org_id="GB-CHC-1", slug="seed-idea", status="seed")
    idea_developing = _idea(org_id="GB-CHC-1", slug="developing-idea", status="developing")
    idea_shaped = _idea(org_id="GB-CHC-1", slug="shaped-idea", status="shaped")

    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    db = _stub_db_with_signals(
        ideas=[idea_delivered, idea_seed, idea_developing, idea_shaped],
        profiles=[profile],
        signal_rows=[],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, sort="status", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == [
        "seed-idea",
        "developing-idea",
        "shaped-idea",
        "delivered-idea",
    ]


async def test_sort_recent_is_the_default_alphabetical_order():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    idea_z = _idea(org_id="GB-CHC-1", slug="zebra", themes=["education"])
    idea_a = _idea(org_id="GB-CHC-1", slug="apple", themes=["education"])
    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    db = _stub_db_with_signals(
        ideas=[idea_z, idea_a],
        profiles=[profile],
        signal_rows=[],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, sort="recent", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    slugs = [r["slug"] for r in body["results"]]
    assert slugs == ["apple", "zebra"]


async def test_idea_row_carries_signal_count():
    from llmstxt_api.routes.open_org_discovery import discover_ideas

    idea = _idea(org_id="GB-CHC-1", slug="popular", themes=["education"])
    profile = _profile(org_id="GB-CHC-1", name="Riverside")
    profile.profile_json = {"identity": {"name": "Riverside"}}

    db = _stub_db_with_signals(
        ideas=[idea],
        profiles=[profile],
        signal_rows=[(idea.id, 5)],
    )

    response = await discover_ideas(
        theme=None, area_code=None, status=None, q=None,
        cost_max=None, sort="recent", cursor=None, limit=20, db=db,
    )
    import json
    body = json.loads(response.body)
    assert body["results"][0]["signal_count"] == 5


# --------------------------------------------------------------------------- #
# Ideas summary endpoint — GET /api/open-org/discover/ideas/summary
# --------------------------------------------------------------------------- #


def _stub_summary_db(*, ideas: list, profiles: list):
    """AsyncSession whose execute() returns ideas then profiles (for summary)."""
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    # Summary issues at most two queries: ideas, then profiles (only if there
    # are org_ids). When there are no ideas, only one query is issued.
    if ideas:
        db.execute.side_effect = [_wrap(ideas), _wrap(profiles)]
    else:
        db.execute.side_effect = [_wrap(ideas)]
    return db


async def test_summary_endpoint_returns_correct_counts():
    from llmstxt_api.routes.open_org_discovery import discover_ideas_summary

    profile_a = _profile(org_id="GB-CHC-A", name="Alpha")
    profile_a.profile_json = {"identity": {"name": "Alpha"}}
    profile_b = _profile(org_id="GB-CHC-B", name="Beta")
    profile_b.profile_json = {"identity": {"name": "Beta"}}

    ideas = [
        _idea(org_id="GB-CHC-A", slug="one", themes=["education", "food_access"], status="seed"),
        _idea(org_id="GB-CHC-A", slug="two", themes=["education"], status="developing"),
        _idea(org_id="GB-CHC-B", slug="three", themes=["health"], status="shaped"),
    ]

    db = _stub_summary_db(ideas=ideas, profiles=[profile_a, profile_b])

    response = await discover_ideas_summary(db=db)
    import json
    body = json.loads(response.body)
    assert body["total_ideas"] == 3
    assert body["total_orgs"] == 2
    assert body["themes_breakdown"]["education"] == 2
    assert body["themes_breakdown"]["food_access"] == 1
    assert body["themes_breakdown"]["health"] == 1
    assert body["status_breakdown"]["seed"] == 1
    assert body["status_breakdown"]["developing"] == 1
    assert body["status_breakdown"]["shaped"] == 1


async def test_summary_endpoint_excludes_ideas_with_unpublished_parent_profile():
    from llmstxt_api.routes.open_org_discovery import discover_ideas_summary

    # Idea whose parent profile is NOT in the published profiles list.
    ideas = [_idea(org_id="GB-CHC-ORPHAN", slug="orphan", themes=["education"])]
    # No published profile for GB-CHC-ORPHAN.
    db = _stub_summary_db(ideas=ideas, profiles=[])

    response = await discover_ideas_summary(db=db)
    import json
    body = json.loads(response.body)
    assert body["total_ideas"] == 0
    assert body["total_orgs"] == 0
    assert body["themes_breakdown"] == {}
    assert body["status_breakdown"] == {}


async def test_summary_endpoint_with_no_published_ideas_returns_zeros():
    from llmstxt_api.routes.open_org_discovery import discover_ideas_summary

    db = _stub_summary_db(ideas=[], profiles=[])

    response = await discover_ideas_summary(db=db)
    import json
    body = json.loads(response.body)
    assert body["total_ideas"] == 0
    assert body["total_orgs"] == 0
    assert body["themes_breakdown"] == {}
    assert body["status_breakdown"] == {}
