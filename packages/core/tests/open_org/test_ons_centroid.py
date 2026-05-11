"""Tests for the LAD-centroid lookup added to ``ons_geography`` for Murmurations.

Murmurations requires a ``geolocation`` for search-by-place. When the
postcodes.io lookup fails (no postcode in CC data), we fall back to the
area centroid stored alongside the LAD code.
"""

from __future__ import annotations

import pytest

from llmstxt_core.open_org import ons_geography


def test_returns_centroid_for_england():
    lat, lon = ons_geography.lookup_lad_centroid("England")
    assert -90 <= lat <= 90
    assert -180 <= lon <= 180


def test_normalises_input_same_as_code_lookup():
    """Case, whitespace, ``Throughout `` prefix all tolerated."""
    a = ons_geography.lookup_lad_centroid("England")
    b = ons_geography.lookup_lad_centroid("  Throughout ENGLAND  ")
    assert a == b


def test_returns_none_when_area_has_code_but_no_centroid():
    """A LAD in the lookup with no centroid block is fine — caller falls back."""
    # Pick a LAD known to be present without centroid coverage. ``Sutton`` is in
    # the table but the centroid map only covers UK nations and major cities.
    assert ons_geography.lookup_lad_code("Sutton") is not None
    assert ons_geography.lookup_lad_centroid("Sutton") is None


def test_returns_none_for_unknown_area():
    assert ons_geography.lookup_lad_centroid("Atlantis") is None


def test_returns_none_for_empty_input():
    assert ons_geography.lookup_lad_centroid("") is None
    assert ons_geography.lookup_lad_centroid(None) is None
    assert ons_geography.lookup_lad_centroid("   ") is None


def test_all_uk_nations_have_centroids():
    """The four UK nations are the most common area_of_operation values from CC;
    they MUST have centroids so the fallback chain finds *something*."""
    for nation in ("England", "Wales", "Scotland", "Northern Ireland"):
        assert ons_geography.lookup_lad_centroid(nation) is not None, nation


def test_centroids_satisfy_uk_bounds():
    """Any centroid in the table must plausibly be in/near the UK."""
    for area, centroid in ons_geography.load_centroid_table().items():
        lat, lon = centroid
        assert 49.0 < lat < 61.0, f"{area} latitude {lat} outside UK"
        assert -9.0 < lon < 2.0, f"{area} longitude {lon} outside UK"
