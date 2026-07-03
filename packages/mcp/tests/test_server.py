"""TDD tests for the openorg-mcp-server public tools.

All tools are plain async functions that accept a db session (AsyncSession)
so they can be tested with ``unittest.mock.AsyncMock`` — no real Postgres
required. The tool functions live in ``openorg_mcp.tools`` and the resource
functions in ``openorg_mcp.resources``.

These tests were written FIRST (red), then the implementation was built to
make them green.
"""

from __future__ import annotations

import json
import uuid
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Model helpers — mirror the fixtures in packages/api/tests/test_open_org_*
# ---------------------------------------------------------------------------


def _profile(
    *,
    org_id: str = "GB-CHC-1234567",
    name: str = "Riverside Trust",
    themes: list[str] | None = None,
    area: str | None = None,
    area_code: str | None = None,
    published: bool = True,
    evidence: list[dict] | None = None,
    summary: str | None = None,
):
    """Build an OrgProfile ORM object with a realistic profile_json payload."""
    from llmstxt_api.open_org_models import OrgProfile

    geography: dict = {}
    if area:
        geography["primary_area"] = area
    if area_code:
        geography["primary_area_code"] = area_code

    mission: dict = {
        "themes": themes or ["education"],
    }
    if summary:
        mission["summary"] = summary

    payload: dict = {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": name,
            "identifiers": {"org_id": org_id},
            "geography": geography,
        },
        "mission": mission,
    }
    if evidence is not None:
        payload["evidence"] = evidence

    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        published=published,
        profile_json=payload,
        generation_status="ready",
    )


def _idea(
    *,
    org_id: str = "GB-CHC-1234567",
    slug: str = "community-kitchen",
    title: str | None = "Community Kitchen",
    themes: list[str] | None = None,
    status: str = "developing",
    published: bool = True,
    summary: str | None = None,
):
    from llmstxt_api.open_org_models import OrgIdea

    idea_json: dict = {
        "schema_version": "open-org-idea/v0.1",
        "id": slug,
        "status": status,
        "themes": themes or ["food_access"],
    }
    if title:
        idea_json["title"] = title
    if summary:
        idea_json["summary"] = summary

    return OrgIdea(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        published=published,
        status=status,
        themes=themes or ["food_access"],
        idea_json=idea_json,
    )


def _strategy(
    *,
    org_id: str = "GB-CHC-1234567",
    slug: str = "2025-2028",
    title: str | None = "2025-2028 Strategy",
    themes: list[str] | None = None,
    published: bool = True,
    summary: str | None = None,
):
    from llmstxt_api.open_org_models import OrgStrategy

    strategy_json: dict = {
        "schema_version": "open-org-strategy/v0.1",
        "id": slug,
        "themes": themes or ["education"],
    }
    if title:
        strategy_json["title"] = title
    if summary:
        strategy_json["summary"] = summary

    return OrgStrategy(
        id=uuid.uuid4(),
        org_id=org_id,
        slug=slug,
        published=published,
        status="active",
        themes=themes or ["education"],
        strategy_json=strategy_json,
    )


def _external(
    *,
    org_id: str = "GB-CHC-999",
    name: str = "Federated Org",
    tags: list[str] | None = None,
):
    from llmstxt_api.open_org_models import ExternalOrgCache

    return ExternalOrgCache(
        id=uuid.uuid4(),
        org_id=org_id,
        source_url=f"https://elsewhere.example/{org_id}",
        profile_json={
            "name": name,
            "tags": tags or ["food_access"],
            "org_id_guide": org_id,
        },
    )


# ---------------------------------------------------------------------------
# DB stub helpers
# ---------------------------------------------------------------------------


def _result(rows):
    """Build a mock execute() result whose .scalars().all() returns ``rows``."""
    return mock.MagicMock(
        scalars=mock.MagicMock(
            return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
        )
    )


def _scalar_result(row):
    """Build a mock execute() result whose .scalar_one_or_none() returns ``row``."""
    return mock.MagicMock(
        scalars=mock.MagicMock(
            return_value=mock.MagicMock(
                one_or_none=mock.MagicMock(return_value=row),
                all=mock.MagicMock(return_value=[row] if row else []),
                first=mock.MagicMock(return_value=row),
            )
        ),
        scalar_one_or_none=mock.MagicMock(return_value=row),
    )


def _stub_db_execute(*results):
    """AsyncSession whose execute() returns the given results in order."""
    db = mock.AsyncMock()
    db.execute.side_effect = list(results)
    return db


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


async def test_get_profile_returns_profile_json_for_published_org():
    from openorg_mcp.tools import get_profile

    profile = _profile(org_id="GB-CHC-1", name="Riverside Trust")
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_profile(db, org_id="GB-CHC-1")

    assert result is not None
    assert result["identity"]["name"] == "Riverside Trust"
    assert result["identity"]["identifiers"]["org_id"] == "GB-CHC-1"


async def test_get_profile_returns_none_for_unpublished_org():
    """No existence leak: unpublished profiles return None, not an error."""
    from openorg_mcp.tools import get_profile

    profile = _profile(org_id="GB-CHC-1", published=False)
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_profile(db, org_id="GB-CHC-1")

    assert result is None


async def test_get_profile_returns_none_for_missing_org():
    from openorg_mcp.tools import get_profile

    db = _stub_db_execute(_scalar_result(None))

    result = await get_profile(db, org_id="GB-CHC-NONEXISTENT")

    assert result is None


async def test_get_profile_returns_none_when_profile_json_is_null():
    from openorg_mcp.tools import get_profile
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1",
        published=True,
        profile_json=None,
        generation_status="ready",
    )
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_profile(db, org_id="GB-CHC-1")

    assert result is None


# ---------------------------------------------------------------------------
# search_profiles
# ---------------------------------------------------------------------------


async def test_search_profiles_returns_matching_orgs():
    from openorg_mcp.tools import search_profiles

    local_rows = [
        _profile(org_id="GB-CHC-1", name="Riverside Trust", themes=["education"]),
        _profile(org_id="GB-CHC-2", name="Aardvark Trust", themes=["food_access"]),
    ]
    external_rows = [
        _external(org_id="GB-CHC-3", name="Magpie Collective", tags=["health"]),
    ]
    db = _stub_db_execute(_result(local_rows), _result(external_rows))

    results = await search_profiles(db)

    assert len(results) == 3
    names = {r["name"] for r in results}
    assert names == {"Riverside Trust", "Aardvark Trust", "Magpie Collective"}


async def test_search_profiles_filters_by_theme():
    from openorg_mcp.tools import search_profiles

    local_rows = [
        _profile(org_id="GB-CHC-1", name="Riverside Trust", themes=["education", "food_access"]),
        _profile(org_id="GB-CHC-2", name="Aardvark Trust", themes=["health"]),
    ]
    external_rows: list = []
    db = _stub_db_execute(_result(local_rows), _result(external_rows))

    results = await search_profiles(db, theme="food_access")

    assert len(results) == 1
    assert results[0]["name"] == "Riverside Trust"


async def test_search_profiles_filters_by_name_query():
    from openorg_mcp.tools import search_profiles

    local_rows = [
        _profile(org_id="GB-CHC-1", name="Riverside Trust"),
        _profile(org_id="GB-CHC-2", name="Aardvark Trust"),
    ]
    external_rows: list = []
    db = _stub_db_execute(_result(local_rows), _result(external_rows))

    results = await search_profiles(db, q="river")

    assert len(results) == 1
    assert results[0]["name"] == "Riverside Trust"


async def test_search_profiles_filters_by_place_area_code():
    from openorg_mcp.tools import search_profiles

    local_rows = [
        _profile(org_id="GB-CHC-1", name="Riverside Trust", area="Norfolk",
                 area_code="E07000147"),
        _profile(org_id="GB-CHC-2", name="Aardvark Trust", area="Cornwall",
                 area_code="E06000052"),
    ]
    external_rows: list = []
    db = _stub_db_execute(_result(local_rows), _result(external_rows))

    results = await search_profiles(db, area_code="E07000147")

    assert len(results) == 1
    assert results[0]["name"] == "Riverside Trust"


async def test_search_profiles_local_wins_over_federated_for_same_org_id():
    from openorg_mcp.tools import search_profiles

    local_rows = [_profile(org_id="GB-CHC-1", name="Local Riverside")]
    external_rows = [_external(org_id="GB-CHC-1", name="Federated Riverside")]
    db = _stub_db_execute(_result(local_rows), _result(external_rows))

    results = await search_profiles(db)

    assert len(results) == 1
    assert results[0]["name"] == "Local Riverside"
    assert results[0]["source"] == "local"


# ---------------------------------------------------------------------------
# get_ideas
# ---------------------------------------------------------------------------


async def test_get_ideas_returns_published_ideas_for_org():
    from openorg_mcp.tools import get_ideas

    ideas = [
        _idea(org_id="GB-CHC-1", slug="kitchen", title="Community Kitchen"),
        _idea(org_id="GB-CHC-1", slug="warm-hub", title="Warm Hub"),
        _idea(org_id="GB-CHC-1", slug="draft-idea", published=False),
    ]
    db = _stub_db_execute(_result(ideas))

    results = await get_ideas(db, org_id="GB-CHC-1")

    assert len(results) == 2
    slugs = {r["slug"] for r in results}
    assert slugs == {"kitchen", "warm-hub"}
    assert results[0]["title"] == "Community Kitchen"


async def test_get_ideas_returns_empty_list_for_org_with_no_ideas():
    from openorg_mcp.tools import get_ideas

    db = _stub_db_execute(_result([]))

    results = await get_ideas(db, org_id="GB-CHC-1")

    assert results == []


# ---------------------------------------------------------------------------
# get_strategies
# ---------------------------------------------------------------------------


async def test_get_strategies_returns_published_strategies_for_org():
    from openorg_mcp.tools import get_strategies

    strategies = [
        _strategy(org_id="GB-CHC-1", slug="2025-2028", title="2025-2028 Strategy"),
        _strategy(org_id="GB-CHC-1", slug="draft-strat", published=False),
    ]
    db = _stub_db_execute(_result(strategies))

    results = await get_strategies(db, org_id="GB-CHC-1")

    assert len(results) == 1
    assert results[0]["slug"] == "2025-2028"
    assert results[0]["title"] == "2025-2028 Strategy"


# ---------------------------------------------------------------------------
# get_evidence
# ---------------------------------------------------------------------------


async def test_get_evidence_extracts_evidence_list_from_profile_json():
    from openorg_mcp.tools import get_evidence

    evidence_items = [
        {"title": "Annual Report 2024", "url": "https://example.com/report.pdf"},
        {"title": "Impact Assessment", "url": "https://example.com/impact.pdf"},
    ]
    profile = _profile(org_id="GB-CHC-1", evidence=evidence_items)
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_evidence(db, org_id="GB-CHC-1")

    assert result is not None
    assert len(result) == 2
    assert result[0]["title"] == "Annual Report 2024"
    assert result[1]["title"] == "Impact Assessment"


async def test_get_evidence_returns_empty_list_when_no_evidence_key():
    from openorg_mcp.tools import get_evidence

    profile = _profile(org_id="GB-CHC-1", evidence=None)
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_evidence(db, org_id="GB-CHC-1")

    assert result == []


async def test_get_evidence_returns_empty_list_for_unpublished_org():
    from openorg_mcp.tools import get_evidence

    profile = _profile(org_id="GB-CHC-1", published=False)
    db = _stub_db_execute(_scalar_result(profile))

    result = await get_evidence(db, org_id="GB-CHC-1")

    assert result == []


# ---------------------------------------------------------------------------
# get_themes
# ---------------------------------------------------------------------------


async def test_get_themes_returns_controlled_vocabulary():
    from openorg_mcp.tools import get_themes

    result = await get_themes()

    assert isinstance(result, list)
    assert len(result) > 0
    # Each theme is a dict with at least a "key" and "label"
    first = result[0]
    assert "key" in first
    assert "label" in first


async def test_get_themes_does_not_require_db_session():
    """get_themes reads from llmstxt_core, not the database."""
    from openorg_mcp.tools import get_themes

    # No db argument needed — confirms it's a pure function over the vocabulary
    result = await get_themes()
    keys = {t["key"] for t in result}
    assert "education" in keys or len(keys) > 0


# ---------------------------------------------------------------------------
# get_graph
# ---------------------------------------------------------------------------


async def test_get_graph_returns_nodes_and_edges():
    from openorg_mcp.tools import get_graph

    profiles = [_profile(org_id="GB-CHC-1", name="Riverside Trust")]
    ideas = [_idea(org_id="GB-CHC-1", slug="kitchen", title="Community Kitchen")]
    strategies: list = []
    db = _stub_db_execute(
        _result(profiles), _result(ideas), _result(strategies)
    )

    result = await get_graph(db)

    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) == 2  # 1 org + 1 idea

    node_ids = {n["id"] for n in result["nodes"]}
    assert "GB-CHC-1" in node_ids
    assert "idea:GB-CHC-1:kitchen" in node_ids

    edge_types = {(e["source"], e["target"], e["type"]) for e in result["edges"]}
    assert ("GB-CHC-1", "idea:GB-CHC-1:kitchen", "org_idea") in edge_types


async def test_get_graph_with_theme_filter():
    from openorg_mcp.tools import get_graph

    profiles = [
        _profile(org_id="GB-CHC-1", name="Riverside Trust", themes=["food_access"]),
        _profile(org_id="GB-CHC-2", name="Aardvark Trust", themes=["health"]),
    ]
    ideas: list = []
    strategies: list = []
    db = _stub_db_execute(
        _result(profiles), _result(ideas), _result(strategies)
    )

    result = await get_graph(db, themes="food_access")

    node_ids = {n["id"] for n in result["nodes"]}
    assert "GB-CHC-1" in node_ids
    assert "GB-CHC-2" not in node_ids


async def test_get_graph_empty_db_returns_empty_nodes_and_edges():
    from openorg_mcp.tools import get_graph

    db = _stub_db_execute(_result([]), _result([]), _result([]))

    result = await get_graph(db)

    assert result["nodes"] == []
    assert result["edges"] == []


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


async def test_read_profile_resource_returns_profile_json():
    from openorg_mcp.resources import read_profile_resource

    profile = _profile(org_id="GB-CHC-1", name="Riverside Trust")
    db = _stub_db_execute(_scalar_result(profile))

    result = await read_profile_resource(db, org_id="GB-CHC-1")

    assert result is not None
    assert result["identity"]["name"] == "Riverside Trust"


async def test_read_idea_resource_returns_single_idea():
    from openorg_mcp.resources import read_idea_resource

    idea = _idea(org_id="GB-CHC-1", slug="community-kitchen", title="Community Kitchen")
    db = _stub_db_execute(_scalar_result(idea))

    result = await read_idea_resource(db, org_id="GB-CHC-1", slug="community-kitchen")

    assert result is not None
    assert result["title"] == "Community Kitchen"
    assert result["slug"] == "community-kitchen"


async def test_read_strategy_resource_returns_single_strategy():
    from openorg_mcp.resources import read_strategy_resource

    strategy = _strategy(org_id="GB-CHC-1", slug="2025-2028", title="2025-2028 Strategy")
    db = _stub_db_execute(_scalar_result(strategy))

    result = await read_strategy_resource(db, org_id="GB-CHC-1", slug="2025-2028")

    assert result is not None
    assert result["title"] == "2025-2028 Strategy"


async def test_read_themes_resource_returns_vocabulary():
    from openorg_mcp.resources import read_themes_resource

    result = await read_themes_resource()

    assert isinstance(result, list)
    assert len(result) > 0
    assert "key" in result[0]


# ---------------------------------------------------------------------------
# Server smoke test — the FastMCP instance should register all 7 tools
# ---------------------------------------------------------------------------


def test_server_registers_all_public_tools():
    import asyncio

    from openorg_mcp.server import create_server

    server = create_server()

    # FastMCP.list_tools() is async; run it in a fresh loop (this is a sync
    # test, so we manage the loop explicitly rather than relying on pytest-
    # asyncio's function-scoped loop).
    loop = asyncio.new_event_loop()
    try:
        tools = loop.run_until_complete(server.list_tools())
    finally:
        loop.close()
    tool_names = {t.name for t in tools}

    expected = {
        "get_profile",
        "search_profiles",
        "get_ideas",
        "get_strategies",
        "get_evidence",
        "get_graph",
        "get_themes",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


def test_server_registers_resources():
    """Resources are registered with their URI templates."""
    import asyncio

    from openorg_mcp.server import create_server

    server = create_server()
    loop = asyncio.new_event_loop()
    try:
        templates = loop.run_until_complete(server.list_resource_templates())
        # Static (non-templated) resources appear in list_resources(), not
        # list_resource_templates().
        resources = loop.run_until_complete(server.list_resources())
    finally:
        loop.close()
    template_uris = {t.uriTemplate for t in templates}
    assert "openorg://orgs/{org_id}/profile" in template_uris
    assert "openorg://orgs/{org_id}/ideas/{slug}" in template_uris
    assert "openorg://orgs/{org_id}/strategies/{slug}" in template_uris
    # openorg://themes is a static URI — it shows up in list_resources()
    static_uris = {str(r.uri) for r in resources}
    assert "openorg://themes" in static_uris