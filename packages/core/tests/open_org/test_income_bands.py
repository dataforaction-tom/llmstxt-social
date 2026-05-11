"""Tests for income band classification."""

import pytest


@pytest.mark.parametrize(
    "income,expected",
    [
        # Lower-bound inclusive, upper exclusive
        (0, "under_10k"),
        (9_999, "under_10k"),
        (10_000, "10k-100k"),
        (99_999, "10k-100k"),
        (100_000, "100k-250k"),
        (249_999, "100k-250k"),
        (250_000, "250k-500k"),
        (499_999, "250k-500k"),
        (500_000, "500k-1m"),
        (999_999, "500k-1m"),
        (1_000_000, "1m-5m"),
        (4_999_999, "1m-5m"),
        (5_000_000, "5m-10m"),
        (9_999_999, "5m-10m"),
        (10_000_000, "10m-100m"),
        (99_999_999, "10m-100m"),
        (100_000_000, "over_100m"),
        (10_000_000_000, "over_100m"),
    ],
)
def test_income_to_band_boundaries(income, expected):
    from llmstxt_core.open_org.income_bands import income_to_band
    assert income_to_band(income) == expected


def test_income_to_band_none_returns_none():
    """Charities with no reported income should map to None, not raise."""
    from llmstxt_core.open_org.income_bands import income_to_band
    assert income_to_band(None) is None


def test_income_to_band_negative_clamps_to_under_10k():
    """Some CC records report £0 / negative for inactive charities."""
    from llmstxt_core.open_org.income_bands import income_to_band
    assert income_to_band(-100) == "under_10k"


def test_income_to_band_accepts_floats():
    from llmstxt_core.open_org.income_bands import income_to_band
    assert income_to_band(10_000.0) == "10k-100k"
    assert income_to_band(9_999.99) == "under_10k"


def test_income_band_enum_exposed():
    """The full enum is exposed for schema generation and validation."""
    from llmstxt_core.open_org.income_bands import INCOME_BANDS
    assert INCOME_BANDS == (
        "under_10k",
        "10k-100k",
        "100k-250k",
        "250k-500k",
        "500k-1m",
        "1m-5m",
        "5m-10m",
        "10m-100m",
        "over_100m",
    )
