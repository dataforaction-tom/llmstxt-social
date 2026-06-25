"""Tests for the public GET /api/open-org/graph route.

Builds a graph of organisations, ideas, and strategies with edges for:
  * org -> idea (direct ownership)
  * org -> strategy (direct ownership)
  * org -> org shared themes (weight = count of shared themes)
  * org -> org shared area (weight 1)

DB is stubbed at the session.execute level, matching the pattern in
``test_open_org_discover_route.py``.
"""

from __future__ import annotations

import json
import uuid
from unittest import mock


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------


def _local(
    *,
    org_id: str,
    name: str,
    themes: list[str] | None = None,
    area: str | None = None,
    income_band: str | None = None,
):
    from llmstxt_api.open_org_models import OrgProfile

    geography: dict = {}
    if area:
        geography["primary_area"] = area
    scale: dict = {}
    if income_band:
        scale["annual_income_band"] = income_band
    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        published=True,
        profile_json={
            "schema_version": "open-org/v0.1",
            "identity": {
                "name": name,
                "identifiers": {"org_id": org_id},
                "geography": geography,
                **({"scale": scale} if scale else {}),
            },
            "mission": {
                "themes": themes or ["education"],
                "summary": f"Summary for {name}",
            },
        },
    )


def _strategy(
    *,
    org_id: str,
    slug: str,
    themes: list[str] | None = None,
    status: str = "active",
    title: str | None = None,
):
    from llmstxt_api.open_org_models import OrgStrategy

    return OrgStrategy(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        published=True,
        status=status,
        themes=themes or ["education"],
        strategy_json={
            "schema_version": "open-org-strategy/v0.1",
            "id": slug,
            "status": status,
            "themes": themes or ["education"],
            **({"title": title} if title else {}),
        },
    )


def _idea(
    *,
    org_id: str,
    slug: str,
    themes: list[str] | None = None,
    status: str = "developing",
    title: str | None = None,
    cost_lower: int | None = None,
    cost_upper: int | None = None,
):
    from llmstxt_api.open_org_models import OrgIdea

    idea_json: dict = {
        "schema_version": "open-org-idea/v0.1",
        "id": slug,
        "status": status,
        "themes": themes or ["education"],
    }
    if title:
        idea_json["title"] = title
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
        status=status,
        themes=themes or ["education"],
        idea_json=idea_json,
    )


def _stub_db(*, profiles: list, ideas: list, strategies: list):
    """AsyncSession whose execute() returns profiles, ideas, strategies."""
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    db.execute.side_effect = [_wrap(profiles), _wrap(ideas), _wrap(strategies)]
    return db


def _body(response) -> dict:
    return json.loads(response.body)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_empty_database_returns_empty_nodes_and_edges():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(profiles=[], ideas=[], strategies=[])
    response = await graph(themes=None, limit=100, db=db)
    body = _body(response)
    assert body["nodes"] == []
    assert body["edges"] == []


async def test_single_org_no_ideas_or_strategies_returns_one_node_no_edges():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Solo Trust")],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["id"] == "GB-CHC-1"
    assert body["nodes"][0]["type"] == "organisation"
    assert body["nodes"][0]["name"] == "Solo Trust"
    assert body["edges"] == []


async def test_org_with_idea_returns_org_node_idea_node_and_org_idea_edge():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Riverside Trust")],
        ideas=[_idea(org_id="GB-CHC-1", slug="kitchen-network", title="Community Kitchen")],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    node_ids = {n["id"] for n in body["nodes"]}
    assert "GB-CHC-1" in node_ids
    assert "idea:GB-CHC-1:kitchen-network" in node_ids

    idea_node = next(n for n in body["nodes"] if n["type"] == "idea")
    assert idea_node["org_id"] == "GB-CHC-1"
    assert idea_node["name"] == "Community Kitchen"

    edge_types = {(e["source"], e["target"], e["type"]) for e in body["edges"]}
    assert ("GB-CHC-1", "idea:GB-CHC-1:kitchen-network", "org_idea") in edge_types


async def test_org_with_strategy_returns_org_node_strategy_node_and_org_strategy_edge():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Riverside Trust")],
        ideas=[],
        strategies=[_strategy(org_id="GB-CHC-1", slug="2025-2028", title="2025-2028 Strategy")],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    node_ids = {n["id"] for n in body["nodes"]}
    assert "strategy:GB-CHC-1:2025-2028" in node_ids

    strat_node = next(n for n in body["nodes"] if n["type"] == "strategy")
    assert strat_node["org_id"] == "GB-CHC-1"

    edge_types = {(e["source"], e["target"], e["type"]) for e in body["edges"]}
    assert ("GB-CHC-1", "strategy:GB-CHC-1:2025-2028", "org_strategy") in edge_types


async def test_two_orgs_with_shared_theme_return_shared_theme_edge_with_weight():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", themes=["food_access", "health", "education"]),
            _local(org_id="GB-CHC-2", name="Beta", themes=["food_access", "health", "mental_health"]),
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared_theme_edges = [
        e for e in body["edges"]
        if e["type"] == "shared_theme"
        and {e["source"], e["target"]} == {"GB-CHC-1", "GB-CHC-2"}
    ]
    assert len(shared_theme_edges) == 1
    assert shared_theme_edges[0]["weight"] == 2  # food_access + health


async def test_two_orgs_with_shared_area_return_shared_area_edge():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", area="Great Yarmouth"),
            _local(org_id="GB-CHC-2", name="Beta", area="Great Yarmouth"),
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared_area_edges = [
        e for e in body["edges"]
        if e["type"] == "shared_area"
        and {e["source"], e["target"]} == {"GB-CHC-1", "GB-CHC-2"}
    ]
    assert len(shared_area_edges) == 1
    assert shared_area_edges[0]["weight"] == 1


async def test_theme_filter_excludes_non_matching_nodes():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Food Org", themes=["food_access"]),
            _local(org_id="GB-CHC-2", name="Edu Org", themes=["education"]),
        ],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="kitchen", themes=["food_access"]),
            _idea(org_id="GB-CHC-2", slug="tutoring", themes=["education"]),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=["food_access"], limit=100, db=db))
    node_ids = {n["id"] for n in body["nodes"]}
    assert "GB-CHC-1" in node_ids
    assert "idea:GB-CHC-1:kitchen" in node_ids
    assert "GB-CHC-2" not in node_ids
    assert "idea:GB-CHC-2:tutoring" not in node_ids


async def test_limit_parameter_caps_org_nodes():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id=f"GB-CHC-{i}", name=f"Org {i}") for i in range(5)
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=2, db=db))
    org_nodes = [n for n in body["nodes"] if n["type"] == "organisation"]
    assert len(org_nodes) == 2


async def test_org_node_includes_income_band_and_ideas_count():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Riverside", income_band="250k-500k")],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="a"),
            _idea(org_id="GB-CHC-1", slug="b"),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    org_node = next(n for n in body["nodes"] if n["type"] == "organisation")
    assert org_node["income_band"] == "250k-500k"
    assert org_node["ideas_count"] == 2


async def test_idea_node_includes_cost_range():
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Riverside")],
        ideas=[_idea(org_id="GB-CHC-1", slug="kitchen", cost_lower=80_000, cost_upper=120_000)],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    idea_node = next(n for n in body["nodes"] if n["type"] == "idea")
    assert idea_node["cost_range"] == [80_000, 120_000]