"""Tests for the Murmurations envelope builder.

The envelope is a flat shape published at /open-org/{org_id}/murmurations.json
that the Murmurations index validates against open_org_profile-v0.1.0. Tests
inject the geolocation lookups so they stay offline.
"""

from __future__ import annotations

import pytest

from llmstxt_core.open_org.murmurations import (
    MURMURATIONS_SCHEMA_NAME,
    build_envelope,
)


def _profile_payload(**overrides) -> dict:
    base = {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": "Acme Aid",
            "registration": {
                "charity_commission_ew": "1234567",
                "companies_house": "01234567",
            },
            "identifiers": {"org_id": "GB-CHC-1234567"},
            "geography": {
                "primary_area": "England",
                "primary_area_code": "E92000001",
            },
            "scale": {"annual_income_band": "100k-250k"},
            "website": "https://acme.example",
            "contact": {"postcode": "NR30 1QH"},
        },
        "mission": {
            "themes": ["education", "children_and_young_people"],
        },
    }
    base.update(overrides)
    return base


async def _postcodes_returning(value):
    async def _lookup(postcode, **kwargs):
        return value

    return _lookup


async def _centroid_returning(value):
    def _lookup(area_name):
        return value

    return _lookup


# --- Happy path ------------------------------------------------------------


async def test_envelope_includes_required_murmurations_fields():
    postcodes_lookup = await _postcodes_returning((52.6074, 1.7295))
    centroid_lookup = await _centroid_returning(None)

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert envelope["linked_schemas"] == [MURMURATIONS_SCHEMA_NAME]
    assert envelope["name"] == "Acme Aid"
    assert envelope["primary_url"] == "https://acme.example"
    assert envelope["org_id_guide"] == "GB-CHC-1234567"
    assert envelope["tags"] == ["education", "children_and_young_people"]
    assert envelope["schema_version"] == "open-org/v0.1"


async def test_envelope_open_org_profile_url_is_canonical():
    postcodes_lookup = await _postcodes_returning((52.6074, 1.7295))
    centroid_lookup = await _centroid_returning(None)

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert (
        envelope["open_org_profile_url"]
        == "https://openorg.good-ship.co.uk/open-org/GB-CHC-1234567/profile.json"
    )


async def test_envelope_strips_trailing_slash_in_base_url():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk/",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )
    assert (
        envelope["open_org_profile_url"]
        == "https://openorg.good-ship.co.uk/open-org/GB-CHC-1234567/profile.json"
    )


# --- Geolocation fallback chain --------------------------------------------


async def test_envelope_uses_postcodes_io_when_available():
    postcodes_lookup = await _postcodes_returning((52.6074, 1.7295))
    centroid_lookup = await _centroid_returning((99.0, 99.0))

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )
    assert envelope["geolocation"] == {"lat": 52.6074, "lon": 1.7295}


async def test_envelope_falls_back_to_lad_centroid_when_postcodes_misses():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning((52.3555, -1.1743))

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )
    assert envelope["geolocation"] == {"lat": 52.3555, "lon": -1.1743}


async def test_envelope_omits_geolocation_when_both_lookups_miss():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )
    assert "geolocation" not in envelope


async def test_envelope_uses_existing_geolocation_if_in_profile():
    """If the profile already has identity.geography.geolocation, we trust it
    and don't waste a postcodes.io call."""
    payload = _profile_payload()
    payload["identity"]["geography"]["geolocation"] = {"lat": 1.0, "lon": 2.0}

    calls = []

    async def _postcodes_lookup(postcode, **kwargs):
        calls.append(postcode)
        return None

    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        payload,
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=_postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert envelope["geolocation"] == {"lat": 1.0, "lon": 2.0}
    assert calls == []  # No outbound call when geolocation is already set.


# --- Primary URL fallback --------------------------------------------------


async def test_primary_url_falls_back_to_open_org_profile_url_if_no_website():
    payload = _profile_payload()
    del payload["identity"]["website"]

    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        payload,
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert envelope["primary_url"] == envelope["open_org_profile_url"]


# --- Optional fields are passed through when present ----------------------


async def test_envelope_includes_strategy_themes_and_ideas_count():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)

    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
        strategy_themes=["food_access", "community_development"],
        ideas_count=3,
    )
    assert envelope["strategy_themes"] == ["food_access", "community_development"]
    assert envelope["ideas_count"] == 3


async def test_envelope_omits_strategy_themes_when_none():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
        strategy_themes=None,
        ideas_count=0,
    )
    # Empty defaults must not pollute the envelope.
    assert "strategy_themes" not in envelope
    assert envelope.get("ideas_count", 0) == 0  # 0 is OK; what we don't want is None.


async def test_envelope_passes_registration_and_area_fields():
    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        _profile_payload(),
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert envelope["registration"] == {
        "charity_commission_ew": "1234567",
        "companies_house": "01234567",
    }
    assert envelope["primary_area"] == "England"
    assert envelope["primary_area_code"] == "E92000001"
    assert envelope["annual_income_band"] == "100k-250k"


async def test_envelope_is_resilient_to_minimal_profile():
    """A profile with just name + themes + org_id must still produce a valid envelope."""
    payload = {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": "Minimal Trust",
            "identifiers": {"org_id": "GB-CHC-9999999"},
        },
        "mission": {"themes": ["education"]},
    }

    postcodes_lookup = await _postcodes_returning(None)
    centroid_lookup = await _centroid_returning(None)
    envelope = await build_envelope(
        payload,
        frontend_base_url="https://openorg.good-ship.co.uk",
        postcodes_io_lookup=postcodes_lookup,
        ons_centroid_lookup=centroid_lookup,
    )

    assert envelope["name"] == "Minimal Trust"
    assert envelope["org_id_guide"] == "GB-CHC-9999999"
    assert envelope["tags"] == ["education"]
    assert "registration" not in envelope
    assert "primary_area" not in envelope
