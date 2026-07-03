"""MCP server setup and tool/resource registration for Open Org.

Exposes Open Org data (profiles, ideas, strategies, evidence, graph, themes)
to AI agents via the Model Context Protocol. This step covers **public
read-only tools only** — no admin tools, no auth (those are Step 8).

Transport
---------
``MCP_TRANSPORT`` env var selects the transport:
  * ``stdio`` (default) — for Claude Desktop and local CLI agents
  * ``streamable-http`` — for remote agents over HTTP

Usage
-----
Run directly:

    python -m openorg_mcp.server

Or via the console script:

    openorg-mcp
"""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from llmstxt_api.database import AsyncSessionLocal

from .resources import (
    read_idea_resource,
    read_profile_resource,
    read_strategy_resource,
    read_themes_resource,
)
from .tools import (
    get_evidence,
    get_graph,
    get_ideas,
    get_profile,
    get_strategies,
    get_themes,
    search_profiles,
)

_SERVER_NAME = "openorg-mcp"


# ---------------------------------------------------------------------------
# Session-scoped tool wrappers
# ---------------------------------------------------------------------------
#
# The underlying tool functions in ``tools.py`` take an ``AsyncSession`` as
# their first argument so they're trivially unit-testable with mocks. The
# wrappers below open a real session via ``AsyncSessionLocal`` and delegate,
# bridging the MCP tool-call interface (which passes plain kwargs) to the
# tool functions. The ``name=`` kwarg on ``@server.tool`` sets the MCP tool
# name that clients see (not the Python function name).


def _register_tools(server: FastMCP) -> None:

    @server.tool(name="get_profile")
    async def _get_profile(org_id: str) -> dict[str, Any] | None:
        """Fetch an organisation's full Open Org profile JSON by org_id.

        Args:
            org_id: The org-id.guide identifier (e.g. GB-CHC-1234567).

        Returns:
            The profile JSON dict, or None if the org is unpublished or not found.
        """
        async with AsyncSessionLocal() as db:
            return await get_profile(db, org_id=org_id)

    @server.tool(name="search_profiles")
    async def _search_profiles(
        theme: str | None = None,
        place: str | None = None,
        q: str | None = None,
        area_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search published Open Org profiles by theme, place, or name.

        Args:
            theme: Theme key to filter on (e.g. "education", "food_access").
            place: Place name filter (mapped to area_code internally).
            q: Free-text search across org name / area / summary.
            area_code: ONS area code (LAD/ITL) to filter by.

        Returns:
            A list of discovery row dicts, each with org_id, name, themes,
            primary_area, profile_url, and source ("local" or "federated").
        """
        async with AsyncSessionLocal() as db:
            return await search_profiles(
                db, theme=theme, place=place, q=q, area_code=area_code
            )

    @server.tool(name="get_ideas")
    async def _get_ideas(org_id: str) -> list[dict[str, Any]]:
        """List published ideas for an organisation.

        Args:
            org_id: The org-id.guide identifier.

        Returns:
            A list of idea JSON dicts, each augmented with slug and org_id.
        """
        async with AsyncSessionLocal() as db:
            return await get_ideas(db, org_id=org_id)

    @server.tool(name="get_strategies")
    async def _get_strategies(org_id: str) -> list[dict[str, Any]]:
        """List published strategies for an organisation.

        Args:
            org_id: The org-id.guide identifier.

        Returns:
            A list of strategy JSON dicts, each augmented with slug and org_id.
        """
        async with AsyncSessionLocal() as db:
            return await get_strategies(db, org_id=org_id)

    @server.tool(name="get_evidence")
    async def _get_evidence(org_id: str) -> list[dict[str, Any]]:
        """List evidence items from an organisation's profile.

        Args:
            org_id: The org-id.guide identifier.

        Returns:
            A list of evidence item dicts (title, url, etc.), or an empty list
            if the org is unpublished, missing, or has no evidence.
        """
        async with AsyncSessionLocal() as db:
            return await get_evidence(db, org_id=org_id)

    @server.tool(name="get_graph")
    async def _get_graph(
        themes: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return the Open Org discovery graph: nodes and edges.

        Nodes are organisations, ideas, and strategies. Edges represent
        ownership (org→idea, org→strategy), shared themes, shared areas,
        and semantic connections.

        Args:
            themes: Comma-separated theme keys to filter nodes by.
            limit: Maximum number of organisation nodes (default 100).

        Returns:
            A dict with "nodes" and "edges" lists, plus a "graph_summary".
        """
        async with AsyncSessionLocal() as db:
            return await get_graph(db, themes=themes, limit=limit)

    @server.tool(name="get_themes")
    async def _get_themes() -> list[dict[str, Any]]:
        """Return the Open Org controlled theme vocabulary.

        Each theme is a dict with "key", "label", and "description".
        No database connection required.
        """
        return await get_themes()


def _register_resources(server: FastMCP) -> None:

    @server.resource("openorg://orgs/{org_id}/profile")
    async def _profile_resource(org_id: str) -> str:
        """Full Open Org profile JSON for an organisation."""
        async with AsyncSessionLocal() as db:
            result = await read_profile_resource(db, org_id=org_id)
            return json.dumps(result) if result is not None else "null"

    @server.resource("openorg://orgs/{org_id}/ideas/{slug}")
    async def _idea_resource(org_id: str, slug: str) -> str:
        """A single published idea by org_id and slug."""
        async with AsyncSessionLocal() as db:
            result = await read_idea_resource(db, org_id=org_id, slug=slug)
            return json.dumps(result) if result is not None else "null"

    @server.resource("openorg://orgs/{org_id}/strategies/{slug}")
    async def _strategy_resource(org_id: str, slug: str) -> str:
        """A single published strategy by org_id and slug."""
        async with AsyncSessionLocal() as db:
            result = await read_strategy_resource(db, org_id=org_id, slug=slug)
            return json.dumps(result) if result is not None else "null"

    @server.resource("openorg://themes")
    async def _themes_resource() -> str:
        """The controlled Open Org theme vocabulary."""
        result = await read_themes_resource()
        return json.dumps(result)


# ---------------------------------------------------------------------------
# Server factory + entry point
# ---------------------------------------------------------------------------


def create_server() -> FastMCP:
    """Create and configure the FastMCP server with all public tools/resources.

    Returns the configured ``FastMCP`` instance (not yet running). Tests can
    call ``list_tools()`` / ``list_resource_templates()`` on the result.
    """
    server = FastMCP(_SERVER_NAME)
    _register_tools(server)
    _register_resources(server)
    return server


def main() -> None:
    """Entry point for ``python -m openorg_mcp.server`` / ``openorg-mcp``."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    server = create_server()
    server.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()