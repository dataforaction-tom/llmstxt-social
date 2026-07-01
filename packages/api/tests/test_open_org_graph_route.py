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
    summary: str | None = None,
    strategy_id: str | None = None,
    priorities: list[dict] | None = None,
    period: dict | None = None,
):
    from llmstxt_api.open_org_models import OrgStrategy

    payload: dict = {
        "schema_version": "open-org-strategy/v0.1",
        "id": strategy_id or slug,
        "status": status,
        "themes": themes or ["education"],
    }
    if title:
        payload["title"] = title
    if summary:
        payload["summary"] = summary
    if priorities is not None:
        payload["priorities"] = priorities
    if period is not None:
        payload["period"] = period
    return OrgStrategy(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        published=True,
        status=status,
        themes=themes or ["education"],
        strategy_json=payload,
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
    summary: str | None = None,
    place: dict | None = None,
    connections: list[dict] | None = None,
    linked_strategy_id: str | None = None,
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
    if summary:
        idea_json["summary"] = summary
    if place is not None:
        idea_json["place"] = place
    if connections is not None:
        idea_json["connections"] = connections
    if linked_strategy_id is not None:
        idea_json["linked_strategy_id"] = linked_strategy_id
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


# ---------------------------------------------------------------------------
# Semantic connection tests (Task 1)
# ---------------------------------------------------------------------------


async def test_strategy_to_idea_edge_via_linked_strategy_id():
    """An idea with linked_strategy_id matching a strategy JSON id creates a
    strategy_idea edge from the strategy node to the idea node."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[
            # Org 2's idea links to org 1's strategy by JSON id
            _idea(
                org_id="GB-CHC-2",
                slug="shared-lunch",
                linked_strategy_id="strat-2025",
            ),
        ],
        strategies=[
            _strategy(
                org_id="GB-CHC-1",
                slug="2025-2028",
                strategy_id="strat-2025",
                title="2025-2028 Strategy",
            ),
        ],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    edge_types = {(e["source"], e["target"], e["type"]) for e in body["edges"]}
    assert (
        "strategy:GB-CHC-1:2025-2028",
        "idea:GB-CHC-2:shared-lunch",
        "strategy_idea",
    ) in edge_types


async def test_idea_idea_shared_theme_edge_with_weight():
    """Two ideas from different orgs sharing at least one theme get an
    idea_idea_shared_theme edge with weight = shared theme count."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="kitchen", themes=["food_access", "health"]),
            _idea(org_id="GB-CHC-2", slug="pantry", themes=["food_access", "mental_health"]),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared = [
        e for e in body["edges"]
        if e["type"] == "idea_idea_shared_theme"
        and {e["source"], e["target"]} == {
            "idea:GB-CHC-1:kitchen",
            "idea:GB-CHC-2:pantry",
        }
    ]
    assert len(shared) == 1
    assert shared[0]["weight"] == 1  # only food_access is shared


async def test_idea_idea_shared_theme_excludes_same_org_ideas():
    """Ideas from the same org don't get idea_idea_shared_theme edges."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Alpha")],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="a", themes=["food_access"]),
            _idea(org_id="GB-CHC-1", slug="b", themes=["food_access"]),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared = [e for e in body["edges"] if e["type"] == "idea_idea_shared_theme"]
    assert shared == []


async def test_idea_idea_shared_place_edge_with_description():
    """Two ideas from different orgs in the same place (matching description,
    case-insensitive) get an idea_idea_shared_place edge with description."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="kitchen",
                place={"description": "Great Yarmouth"},
            ),
            _idea(
                org_id="GB-CHC-2",
                slug="pantry",
                place={"description": "great yarmouth"},
            ),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared = [
        e for e in body["edges"]
        if e["type"] == "idea_idea_shared_place"
        and {e["source"], e["target"]} == {
            "idea:GB-CHC-1:kitchen",
            "idea:GB-CHC-2:pantry",
        }
    ]
    assert len(shared) == 1
    assert shared[0]["description"] == "Both in Great Yarmouth"


async def test_idea_idea_shared_place_via_area_codes_overlap():
    """Two ideas from different orgs with overlapping area_codes get an
    idea_idea_shared_place edge."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="a",
                place={"area_codes": ["E06000010"]},
            ),
            _idea(
                org_id="GB-CHC-2",
                slug="b",
                place={"area_codes": ["E06000010", "E06000011"]},
            ),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared = [e for e in body["edges"] if e["type"] == "idea_idea_shared_place"]
    assert len(shared) == 1


async def test_idea_org_connection_edge_with_relationship_label():
    """An idea with a connection to a published org gets an idea_org_connection
    edge from the idea node to the org node, labelled with the relationship."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="kitchen",
                connections=[
                    {"org_name": "Beta", "org_id": "GB-CHC-2", "relationship": "complementary"},
                ],
            ),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    conn = [
        e for e in body["edges"]
        if e["type"] == "idea_org_connection"
        and e["source"] == "idea:GB-CHC-1:kitchen"
        and e["target"] == "GB-CHC-2"
    ]
    assert len(conn) == 1
    assert conn[0]["relationship"] == "complementary"


async def test_idea_org_connection_ignores_non_published_orgs():
    """A connection to an org_id that isn't in the graph produces no edge."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Alpha")],
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="kitchen",
                connections=[
                    {"org_name": "Ghost", "org_id": "GB-CHC-999", "relationship": "collaborating"},
                ],
            ),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    assert [e for e in body["edges"] if e["type"] == "idea_org_connection"] == []


async def test_strategy_strategy_shared_theme_edge_with_weight():
    """Two strategies from different orgs with shared themes get a
    strategy_strategy_shared_theme edge with weight = shared count."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha"),
            _local(org_id="GB-CHC-2", name="Beta"),
        ],
        ideas=[],
        strategies=[
            _strategy(org_id="GB-CHC-1", slug="s1", themes=["food_access", "health"]),
            _strategy(org_id="GB-CHC-2", slug="s2", themes=["food_access", "education"]),
        ],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    shared = [
        e for e in body["edges"]
        if e["type"] == "strategy_strategy_shared_theme"
        and {e["source"], e["target"]} == {
            "strategy:GB-CHC-1:s1",
            "strategy:GB-CHC-2:s2",
        }
    ]
    assert len(shared) == 1
    assert shared[0]["weight"] == 1  # only food_access


async def test_idea_node_carries_summary_field():
    """An idea node's summary comes from idea_json['summary']."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Alpha")],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="kitchen", summary="A community kitchen."),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    idea_node = next(n for n in body["nodes"] if n["type"] == "idea")
    assert idea_node["summary"] == "A community kitchen."


async def test_strategy_node_carries_summary_field():
    """A strategy node's summary comes from strategy_json['summary']."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[_local(org_id="GB-CHC-1", name="Alpha")],
        ideas=[],
        strategies=[
            _strategy(org_id="GB-CHC-1", slug="2025", summary="Three-year plan."),
        ],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    strat_node = next(n for n in body["nodes"] if n["type"] == "strategy")
    assert strat_node["summary"] == "Three-year plan."


async def test_graph_summary_field_counts_nodes_and_edges():
    """The graph payload includes a summary with total counts by type and
    a clusters list."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", themes=["food_access"]),
            _local(org_id="GB-CHC-2", name="Beta", themes=["food_access"]),
        ],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="k1", themes=["food_access"]),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    summary = body["graph_summary"]
    assert summary["total_nodes"] == len(body["nodes"])
    assert summary["total_edges"] == len(body["edges"])
    assert summary["organisations"] == 2
    assert summary["ideas"] == 1
    assert summary["strategies"] == 0
    # The two orgs + idea form a connected cluster
    assert isinstance(summary["clusters"], list)
    assert len(summary["clusters"]) >= 1
    cluster = summary["clusters"][0]
    assert "description" in cluster
    assert "themes" in cluster


async def test_theme_filter_still_works_with_new_edge_types():
    """The theme filter still excludes nodes and edges for non-matching
    themes, even with the new semantic edges."""
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
    assert "idea:GB-CHC-1:kitchen" in node_ids
    assert "idea:GB-CHC-2:tutoring" not in node_ids
    # No idea_idea edges because only one idea survived the filter
    assert [e for e in body["edges"] if e["type"].startswith("idea_idea")] == []


# ---------------------------------------------------------------------------
# Meaningful cluster insights (enhanced graph summary)
# ---------------------------------------------------------------------------


async def test_cluster_description_includes_org_names_ideas_summary_places_dominant_themes():
    """Each cluster surfaces org_names, ideas_summary, places, dominant_themes,
    edge_count, and a human-readable description sentence."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Riverside Trust", themes=["food_access", "social_prescribing"]),
            _local(org_id="GB-CHC-2", name="Norfolk Food Network", themes=["food_access", "social_prescribing"]),
            _local(org_id="GB-CHC-3", name="Age UK Norfolk", themes=["food_access", "social_prescribing"]),
        ],
        ideas=[
            _idea(
                org_id="GB-CHC-1",
                slug="k1",
                themes=["food_access"],
                summary="Hot meals for families",
                place={"description": "Great Yarmouth"},
            ),
            _idea(
                org_id="GB-CHC-2",
                slug="k2",
                themes=["social_prescribing"],
                summary="Social prescribing pilots",
                place={"description": "Great Yarmouth"},
            ),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    clusters = body["graph_summary"]["clusters"]
    assert len(clusters) == 1
    c = clusters[0]
    assert set(c["org_names"]) == {"Riverside Trust", "Norfolk Food Network", "Age UK Norfolk"}
    assert c["ideas_summary"] is not None
    assert "Hot meals" in c["ideas_summary"]
    assert "Great Yarmouth" in c["places"]
    assert "food_access" in c["dominant_themes"]
    assert "social_prescribing" in c["dominant_themes"]
    assert len(c["dominant_themes"]) <= 3
    assert c["edge_count"] >= 1
    assert "Riverside Trust" in c["description"]
    assert "Great Yarmouth" in c["description"]


async def test_cluster_themes_sorted_by_frequency_most_common_first():
    """The cluster's `themes` list is sorted by frequency (most common first)."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", themes=["food_access", "health"]),
            _local(org_id="GB-CHC-2", name="Beta", themes=["food_access", "health"]),
            _local(org_id="GB-CHC-3", name="Gamma", themes=["food_access", "education"]),
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    c = body["graph_summary"]["clusters"][0]
    # food_access appears on all 3 orgs; health on 2; education on 1.
    assert c["themes"][:2] == ["food_access", "health"]
    assert c["dominant_themes"][0] == "food_access"


async def test_cluster_ideas_summary_truncated_to_200_chars():
    """ideas_summary concatenates idea summaries and is capped at 200 chars."""
    from llmstxt_api.routes.open_org_discovery import graph

    long_summary = "A" * 300
    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", themes=["food_access"]),
            _local(org_id="GB-CHC-2", name="Beta", themes=["food_access"]),
        ],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="k1", themes=["food_access"], summary=long_summary),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    c = body["graph_summary"]["clusters"][0]
    assert c["ideas_summary"] is not None
    assert len(c["ideas_summary"]) <= 200


async def test_nodes_in_cluster_get_cluster_id_isolated_nodes_get_null():
    """Nodes in a ≥2-node connected component receive a cluster_id; isolated
    nodes (no edges) get cluster_id: null."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Alpha", themes=["food_access"]),
            _local(org_id="GB-CHC-2", name="Beta", themes=["food_access"]),
            _local(org_id="GB-CHC-3", name="Gamma", themes=["education"]),  # isolated
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    by_id = {n["id"]: n for n in body["nodes"]}
    assert by_id["GB-CHC-1"]["cluster_id"] is not None
    assert by_id["GB-CHC-2"]["cluster_id"] is not None
    assert by_id["GB-CHC-1"]["cluster_id"] == by_id["GB-CHC-2"]["cluster_id"]
    assert by_id["GB-CHC-3"]["cluster_id"] is None


async def test_clusters_sorted_by_size_largest_first():
    """Multiple clusters are returned largest first; cluster_id maps to nodes."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="A1", themes=["food_access"]),
            _local(org_id="GB-CHC-2", name="A2", themes=["food_access"]),
            _local(org_id="GB-CHC-3", name="A3", themes=["food_access"]),
            _local(org_id="GB-CHC-4", name="B1", themes=["education"]),
            _local(org_id="GB-CHC-5", name="B2", themes=["education"]),
        ],
        ideas=[],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    clusters = body["graph_summary"]["clusters"]
    assert len(clusters) == 2
    assert clusters[0]["node_count"] == 3
    assert clusters[1]["node_count"] == 2
    assert clusters[0]["node_count"] >= clusters[1]["node_count"]


async def test_cluster_description_sentence_format_matches_spec():
    """The description reads like 'N organisations (Name, Name) and M ideas around theme in Place'."""
    from llmstxt_api.routes.open_org_discovery import graph

    db = _stub_db(
        profiles=[
            _local(org_id="GB-CHC-1", name="Riverside Trust", themes=["food_access", "social_prescribing"]),
            _local(org_id="GB-CHC-2", name="Norfolk Food Network", themes=["food_access", "social_prescribing"]),
            _local(org_id="GB-CHC-3", name="Age UK Norfolk", themes=["food_access", "social_prescribing"]),
        ],
        ideas=[
            _idea(org_id="GB-CHC-1", slug="k1", themes=["food_access"], summary="Hot meals", place={"description": "Great Yarmouth"}),
            _idea(org_id="GB-CHC-2", slug="k2", themes=["social_prescribing"], summary="Prescribing", place={"description": "Great Yarmouth"}),
            _idea(org_id="GB-CHC-3", slug="k3", themes=["food_access"], summary="Pantry", place={"description": "Great Yarmouth"}),
        ],
        strategies=[],
    )
    body = _body(await graph(themes=None, limit=100, db=db))
    c = body["graph_summary"]["clusters"][0]
    desc = c["description"]
    assert "3 organisations" in desc
    assert "Riverside Trust" in desc
    assert "Age UK Norfolk" in desc
    assert "3 ideas" in desc
    assert "Great Yarmouth" in desc