"""Tests for the public themes vocabulary endpoint.

GET /api/open-org/themes returns the controlled vocabulary keyed list. The
discovery page uses it to populate the filter dropdown. Public so the SPA can
hit it without auth.
"""

from __future__ import annotations

import json
from unittest import mock


def test_themes_endpoint_returns_full_vocabulary():
    from llmstxt_api.routes.open_org_discovery import get_themes

    response = get_themes()
    body = json.loads(response.body)

    assert isinstance(body, list)
    assert len(body) >= 30
    sample = body[0]
    assert {"key", "label", "description"} <= set(sample.keys())


def test_themes_endpoint_includes_known_keys():
    from llmstxt_api.routes.open_org_discovery import get_themes

    body = json.loads(get_themes().body)
    keys = {t["key"] for t in body}
    assert "education" in keys
    assert "older_people" in keys
    assert "children_and_young_people" in keys


def test_themes_endpoint_sets_long_cache_header():
    """Theme vocabulary is stable; let browsers + CDN cache aggressively."""
    from llmstxt_api.routes.open_org_discovery import get_themes

    response = get_themes()
    cache_control = response.headers.get("cache-control", "")
    assert "max-age" in cache_control
