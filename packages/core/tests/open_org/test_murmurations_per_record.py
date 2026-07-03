"""Tests for per-record Murmurations envelopes (strategy + idea).

Phase 1 only submits the profile envelope to the Murmurations index.
Phase 2 adds strategy and idea schemas so individual strategies and ideas
can be federated and discovered independently.

Tests cover:
- build_strategy_envelope: maps org_strategy JSON to flat Murmurations shape
- build_idea_envelope: maps org_idea JSON to flat Murmurations shape
- Schema constants for the new Murmurations schema names
"""

import pytest

from llmstxt_core.open_org.murmurations import (
    MURMURATIONS_SCHEMA_NAME,
    build_envelope,
)
from llmstxt_core.open_org.murmurations_per_record import (
    MURMURATIONS_STRATEGY_SCHEMA_NAME,
    MURMURATIONS_IDEA_SCHEMA_NAME,
    build_strategy_envelope,
    build_idea_envelope,
)


# ---------------------------------------------------------------------------
# Schema name constants
# ---------------------------------------------------------------------------


def test_strategy_schema_name_is_versioned():
    assert MURMURATIONS_STRATEGY_SCHEMA_NAME == "open_org_strategy-v0.1.0"


def test_idea_schema_name_is_versioned():
    assert MURMURATIONS_IDEA_SCHEMA_NAME == "open_org_idea-v0.1.0"


def test_schema_names_differ_from_profile():
    assert MURMURATIONS_STRATEGY_SCHEMA_NAME != MURMURATIONS_SCHEMA_NAME
    assert MURMURATIONS_IDEA_SCHEMA_NAME != MURMURATIONS_SCHEMA_NAME


# ---------------------------------------------------------------------------
# build_strategy_envelope
# ---------------------------------------------------------------------------


_STRATEGY_JSON = {
    "schema_version": "open-org-strategy/v0.1",
    "id": "food-network-strategy",
    "status": "active",
    "themes": ["food_access", "community_development"],
    "period": {"start": "2024-01-01", "end": "2026-12-31", "horizon": "3_5_years"},
    "summary": "Build a sustainable food network across the borough.",
    "not_doing": ["Direct food distribution to individuals"],
    "relationships": [
        {"org_id": "GB-CHC-2222222", "type": "delivery_partner", "name": "Southtown Food Bank"},
    ],
    "funding_mix": [{"source": "National Lottery", "amount": 150000, "status": "secured"}],
    "learning": ["Pilot showed 3-month lead time for new hubs"],
}


def test_build_strategy_envelope_returns_dict_with_linked_schemas():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["linked_schemas"] == [MURMURATIONS_STRATEGY_SCHEMA_NAME]


def test_build_strategy_envelope_includes_org_id():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["org_id_guide"] == "GB-CHC-1234567"


def test_build_strategy_envelope_includes_slug():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["strategy_slug"] == "food-network-strategy"


def test_build_strategy_envelope_includes_themes():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["tags"] == ["food_access", "community_development"]


def test_build_strategy_envelope_includes_status():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["status"] == "active"


def test_build_strategy_envelope_includes_summary():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["summary"] == "Build a sustainable food network across the borough."


def test_build_strategy_envelope_includes_period():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["period_start"] == "2024-01-01"
    assert env["period_end"] == "2026-12-31"
    assert env["period_horizon"] == "3_5_years"


def test_build_strategy_envelope_includes_strategy_url():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert "open_org_strategy_url" in env
    assert "food-network-strategy" in env["open_org_strategy_url"]
    assert "GB-CHC-1234567" in env["open_org_strategy_url"]


def test_build_strategy_envelope_includes_schema_version():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["schema_version"] == "open-org-strategy/v0.1"


def test_build_strategy_envelope_handles_missing_optional_fields():
    minimal = {
        "schema_version": "open-org-strategy/v0.1",
        "id": "minimal-strategy",
        "status": "draft",
        "themes": ["education"],
    }
    env = build_strategy_envelope(
        minimal,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["summary"] is None
    assert env["period_start"] is None
    assert env["period_end"] is None
    assert env["period_horizon"] is None


def test_build_strategy_envelope_strips_trailing_slash_from_base_url():
    env = build_strategy_envelope(
        _STRATEGY_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk/",
    )
    assert not env["open_org_strategy_url"].endswith("//")


# ---------------------------------------------------------------------------
# build_idea_envelope
# ---------------------------------------------------------------------------


_IDEA_JSON = {
    "schema_version": "open-org-idea/v0.1",
    "id": "community-kitchen",
    "status": "shaped",
    "summary": "A community kitchen serving 50 meals/day in Great Yarmouth.",
    "detail": "We will open a community kitchen in the Nelson ward...",
    "themes": ["food_access", "community_development"],
    "place": {
        "description": "Great Yarmouth",
        "area_codes": ["E07000145"],
        "geolocation": {"lat": 52.5778, "lon": 1.7221},
    },
    "cost_range": {"min": 15000, "max": 25000, "currency": "GBP"},
    "evidence_base": [
        {"evidence_id": "ev1", "title": "Pilot data", "evidence_type": "outcome_data"},
    ],
}


def test_build_idea_envelope_returns_dict_with_linked_schemas():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["linked_schemas"] == [MURMURATIONS_IDEA_SCHEMA_NAME]


def test_build_idea_envelope_includes_org_id():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["org_id_guide"] == "GB-CHC-1234567"


def test_build_idea_envelope_includes_slug():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["idea_slug"] == "community-kitchen"


def test_build_idea_envelope_includes_themes():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["tags"] == ["food_access", "community_development"]


def test_build_idea_envelope_includes_status():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["status"] == "shaped"


def test_build_idea_envelope_includes_summary():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert "community kitchen" in env["summary"].lower()


def test_build_idea_envelope_includes_geolocation_from_place():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["geolocation"]["lat"] == 52.5778
    assert env["geolocation"]["lon"] == 1.7221


def test_build_idea_envelope_includes_place_description():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["primary_area"] == "Great Yarmouth"


def test_build_idea_envelope_includes_cost_range():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["cost_min"] == 15000
    assert env["cost_max"] == 25000
    assert env["cost_currency"] == "GBP"


def test_build_idea_envelope_includes_idea_url():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert "open_org_idea_url" in env
    assert "community-kitchen" in env["open_org_idea_url"]
    assert "GB-CHC-1234567" in env["open_org_idea_url"]


def test_build_idea_envelope_includes_schema_version():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["schema_version"] == "open-org-idea/v0.1"


def test_build_idea_envelope_handles_missing_optional_fields():
    minimal = {
        "schema_version": "open-org-idea/v0.1",
        "id": "bare-idea",
        "status": "seed",
        "themes": ["education"],
    }
    env = build_idea_envelope(
        minimal,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["summary"] is None
    assert env["geolocation"] is None
    assert env["primary_area"] is None
    assert env["cost_min"] is None
    assert env["cost_max"] is None


def test_build_idea_envelope_handles_missing_geolocation():
    idea_no_geo = {**_IDEA_JSON}
    idea_no_geo["place"] = {"description": "Great Yarmouth"}
    env = build_idea_envelope(
        idea_no_geo,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk",
    )
    assert env["geolocation"] is None
    assert env["primary_area"] == "Great Yarmouth"


def test_build_idea_envelope_strips_trailing_slash_from_base_url():
    env = build_idea_envelope(
        _IDEA_JSON,
        org_id="GB-CHC-1234567",
        frontend_base_url="https://openorg.good-ship.co.uk/",
    )
    assert not env["open_org_idea_url"].endswith("//")