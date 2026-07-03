"""Per-record Murmurations envelopes for strategies and ideas.

Phase 1 only submits the organisation profile envelope to the Murmurations
index. Phase 2 adds strategy and idea envelopes so individual strategies and
ideas can be federated and discovered independently.

Each envelope is a thin/discovery schema — the Murmurations index stores
discovery-relevant fields; the full record is fetched separately via the
``open_org_strategy_url`` / ``open_org_idea_url``.
"""

from __future__ import annotations

from typing import Any


MURMURATIONS_STRATEGY_SCHEMA_NAME = "open_org_strategy-v0.1.0"
MURMURATIONS_IDEA_SCHEMA_NAME = "open_org_idea-v0.1.0"


def build_strategy_envelope(
    strategy_json: dict,
    *,
    org_id: str,
    frontend_base_url: str,
) -> dict[str, Any]:
    """Build the flat Murmurations envelope for a published Open Org strategy.

    Args:
        strategy_json: The strategy record JSON (from ``OrgStrategy.strategy_json``).
        org_id: The organisation's org-id.guide identifier (e.g. ``GB-CHC-1234567``).
        frontend_base_url: Base URL where the strategy JSON is served.

    Returns:
        Flat dict matching ``open_org_strategy-v0.1.0`` schema.
    """
    base = frontend_base_url.rstrip("/")
    slug = strategy_json.get("id") or ""
    strategy_url = f"{base}/open-org/{org_id}/strategies/{slug}.json"

    period = strategy_json.get("period") or {}

    return {
        "linked_schemas": [MURMURATIONS_STRATEGY_SCHEMA_NAME],
        "org_id_guide": org_id,
        "strategy_slug": slug,
        "name": strategy_json.get("summary") or slug,
        "summary": strategy_json.get("summary"),
        "status": strategy_json.get("status"),
        "tags": list(strategy_json.get("themes") or []),
        "period_start": period.get("start"),
        "period_end": period.get("end"),
        "period_horizon": period.get("horizon"),
        "schema_version": strategy_json.get("schema_version", "open-org-strategy/v0.1"),
        "open_org_strategy_url": strategy_url,
    }


def build_idea_envelope(
    idea_json: dict,
    *,
    org_id: str,
    frontend_base_url: str,
) -> dict[str, Any]:
    """Build the flat Murmurations envelope for a published Open Org idea.

    Args:
        idea_json: The idea record JSON (from ``OrgIdea.idea_json``).
        org_id: The organisation's org-id.guide identifier (e.g. ``GB-CHC-1234567``).
        frontend_base_url: Base URL where the idea JSON is served.

    Returns:
        Flat dict matching ``open_org_idea-v0.1.0`` schema.
    """
    base = frontend_base_url.rstrip("/")
    slug = idea_json.get("id") or ""
    idea_url = f"{base}/open-org/{org_id}/ideas/{slug}.json"

    place = idea_json.get("place") or {}
    geolocation = place.get("geolocation")
    cost_range = idea_json.get("cost_range") or {}

    return {
        "linked_schemas": [MURMURATIONS_IDEA_SCHEMA_NAME],
        "org_id_guide": org_id,
        "idea_slug": slug,
        "name": idea_json.get("summary") or slug,
        "summary": idea_json.get("summary"),
        "status": idea_json.get("status"),
        "tags": list(idea_json.get("themes") or []),
        "primary_area": place.get("description"),
        "geolocation": {
            "lat": geolocation["lat"],
            "lon": geolocation["lon"],
        }
        if isinstance(geolocation, dict)
        and isinstance(geolocation.get("lat"), (int, float))
        and isinstance(geolocation.get("lon"), (int, float))
        else None,
        "cost_min": cost_range.get("min") if cost_range else None,
        "cost_max": cost_range.get("max") if cost_range else None,
        "cost_currency": cost_range.get("currency") if cost_range else None,
        "schema_version": idea_json.get("schema_version", "open-org-idea/v0.1"),
        "open_org_idea_url": idea_url,
    }


__all__ = [
    "MURMURATIONS_STRATEGY_SCHEMA_NAME",
    "MURMURATIONS_IDEA_SCHEMA_NAME",
    "build_strategy_envelope",
    "build_idea_envelope",
]