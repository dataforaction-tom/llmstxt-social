"""Charity Commission annual-income → Open Org income band mapping.

Bands mirror the CC's published income brackets. The mapping is total over
the integer line: any non-negative income lands in exactly one band, negatives
clamp to ``under_10k`` (some CC records report £0/negative for dormant charities),
and ``None`` is preserved (charities with no filing yet).
"""

from __future__ import annotations

INCOME_BANDS: tuple[str, ...] = (
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

# (upper_exclusive, band_label). The last entry catches anything ≥ 100m.
_BOUNDARIES: tuple[tuple[float, str], ...] = (
    (10_000, "under_10k"),
    (100_000, "10k-100k"),
    (250_000, "100k-250k"),
    (500_000, "250k-500k"),
    (1_000_000, "500k-1m"),
    (5_000_000, "1m-5m"),
    (10_000_000, "5m-10m"),
    (100_000_000, "10m-100m"),
)


def income_to_band(income: float | int | None) -> str | None:
    """Return the income band label for a numeric income.

    Returns ``None`` if the input is ``None`` (charity has not filed yet).
    """
    if income is None:
        return None
    for upper_exclusive, label in _BOUNDARIES:
        if income < upper_exclusive:
            return label
    return "over_100m"
