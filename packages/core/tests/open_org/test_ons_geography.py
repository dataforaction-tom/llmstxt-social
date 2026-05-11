"""Tests for the ONS LAD/geography code lookup used by the profile generator.

Why a local table at all: the CC API returns area names like "England" or
"Birmingham", but the Open Org profile schema requires an ONS code matching
``^[A-Z][0-9]{8}$``. A local table covers the common cases without a network
call per generation; ``refresh_from_ons`` keeps it fresh from the ONS Open
Geography Portal when the user runs it explicitly.
"""

from __future__ import annotations

import json

import pytest

from llmstxt_core.open_org import ons_geography


# --- Lookup behaviour --------------------------------------------------------


def test_lookup_returns_none_for_unknown_area():
    assert ons_geography.lookup_lad_code("Atlantis") is None


def test_lookup_is_case_insensitive():
    assert ons_geography.lookup_lad_code("england") == "E92000001"
    assert ons_geography.lookup_lad_code("ENGLAND") == "E92000001"
    assert ons_geography.lookup_lad_code("England") == "E92000001"


def test_lookup_strips_whitespace():
    assert ons_geography.lookup_lad_code("  England  ") == "E92000001"


def test_lookup_strips_throughout_prefix():
    """CC frequently records areas as ``Throughout England``, ``Throughout the UK`` etc."""
    assert ons_geography.lookup_lad_code("Throughout England") == "E92000001"
    assert ons_geography.lookup_lad_code("Throughout Wales") == "W92000004"


def test_lookup_returns_country_codes_for_uk_nations():
    assert ons_geography.lookup_lad_code("England") == "E92000001"
    assert ons_geography.lookup_lad_code("Wales") == "W92000004"
    assert ons_geography.lookup_lad_code("Scotland") == "S92000003"
    assert ons_geography.lookup_lad_code("Northern Ireland") == "N92000002"


def test_lookup_returns_none_for_empty_input():
    assert ons_geography.lookup_lad_code("") is None
    assert ons_geography.lookup_lad_code("   ") is None


def test_lookup_codes_match_open_org_schema_pattern():
    """Every code in the table must match ``^[A-Z][0-9]{8}$``.

    The Open Org profile schema rejects anything else and the generator would
    silently produce invalid profiles otherwise.
    """
    import re

    pattern = re.compile(r"^[A-Z][0-9]{8}$")
    for area, code in ons_geography.load_lookup_table().items():
        assert pattern.match(code), f"{area!r} -> {code!r} doesn't match pattern"


# --- Refresh from ONS --------------------------------------------------------


def test_refresh_from_ons_writes_entries(tmp_path, monkeypatch):
    """``refresh_from_ons`` calls the ONS API and rewrites the lookup file.

    We mock the ``httpx.Client`` so this test runs offline and stays
    deterministic. A real call goes to the ONS Open Geography Portal.
    """
    target_file = tmp_path / "ons_lad_lookup.json"
    monkeypatch.setattr(ons_geography, "_LOOKUP_PATH", target_file)
    ons_geography.load_lookup_table.cache_clear()

    class _FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "features": [
                    {
                        "attributes": {
                            "LAD24NM": "Birmingham",
                            "LAD24CD": "E08000025",
                        }
                    },
                    {
                        "attributes": {
                            "LAD24NM": "Manchester",
                            "LAD24CD": "E08000003",
                        }
                    },
                ]
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            return _FakeResponse()

    written = ons_geography.refresh_from_ons(http_client_factory=_FakeClient)
    assert written >= 2

    data = json.loads(target_file.read_text())
    assert data["entries"]["birmingham"] == "E08000025"
    assert data["entries"]["manchester"] == "E08000003"
    # UK nations must always be present even after refresh.
    assert data["entries"]["england"] == "E92000001"


def test_refresh_from_ons_raises_on_http_failure(tmp_path, monkeypatch):
    """A failing ONS call propagates so the operator sees it; it must not
    silently corrupt the on-disk table."""
    target_file = tmp_path / "ons_lad_lookup.json"
    target_file.write_text(json.dumps({"entries": {"england": "E92000001"}}))
    monkeypatch.setattr(ons_geography, "_LOOKUP_PATH", target_file)

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            class _R:
                status_code = 500
                text = "boom"

                def json(self):
                    raise ValueError("not json")

            return _R()

    with pytest.raises(ons_geography.OnsRefreshError):
        ons_geography.refresh_from_ons(http_client_factory=_BoomClient)

    # On-disk file is unchanged.
    data = json.loads(target_file.read_text())
    assert data["entries"]["england"] == "E92000001"
