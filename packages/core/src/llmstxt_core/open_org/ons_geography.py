"""Lookup an ONS area code from a Charity Commission area name.

The Open Org profile schema requires ``identity.geography.primary_area_code`` to
match ``^[A-Z][0-9]{8}$``. CC API responses give us area names instead, so a
mapping layer is needed. The local lookup table at
``data/ons_lad_lookup.json`` covers UK nations plus the most common Local
Authority Districts (LAD24CD codes from the ONS Open Geography Portal).

When the local table doesn't cover an area the lookup returns ``None`` — the
generator records the name without a code rather than failing the whole
profile. ``refresh_from_ons`` rewrites the table from the official ONS service
and is invoked manually (e.g. via a CLI command); it is *not* called at import
time so tests stay offline.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import httpx


_LOOKUP_PATH = Path(__file__).resolve().parent / "data" / "ons_lad_lookup.json"


_BASE_NATION_CODES = {
    "england": "E92000001",
    "wales": "W92000004",
    "scotland": "S92000003",
    "northern ireland": "N92000002",
    "united kingdom": "K02000001",
    "great britain": "K03000001",
    "england and wales": "K04000001",
}


_THROUGHOUT_PREFIXES = ("throughout the ", "throughout ")


# Default ONS Open Geography Portal endpoint for current LADs (24 series).
# This is a convention; the user can override per call.
_ONS_LAD_FEATURE_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_May_2024_Boundaries_UK_BUC/FeatureServer/0/query"
)


class OnsRefreshError(RuntimeError):
    """Raised when ``refresh_from_ons`` cannot fetch or parse the upstream data."""


@lru_cache(maxsize=1)
def _load_raw_data() -> dict:
    with _LOOKUP_PATH.open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_lookup_table() -> dict[str, str]:
    """Return the area-name → ONS-code mapping (lowercase keys)."""
    data = _load_raw_data()
    entries = data.get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError(f"Malformed ONS lookup file at {_LOOKUP_PATH}")
    # Defensive: ensure all keys are lowercase. The file is hand-curated, but
    # a stray uppercase key would silently miss every lookup.
    return {str(k).lower(): str(v) for k, v in entries.items()}


@lru_cache(maxsize=1)
def load_centroid_table() -> dict[str, tuple[float, float]]:
    """Return area-name → (lat, lon) for the sparse centroid map.

    Coverage is intentionally partial — only areas where we have a reasonable
    centroid value. Used as a fallback when postcodes.io can't resolve.
    """
    data = _load_raw_data()
    raw = data.get("centroids", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, tuple[float, float]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        lat = value.get("lat")
        lon = value.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            out[str(key).lower()] = (float(lat), float(lon))
    return out


def _normalise(area_name: str) -> str:
    name = area_name.strip().lower()
    for prefix in _THROUGHOUT_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break
    return name


def lookup_lad_code(area_name: str | None) -> str | None:
    """Return the ONS code for ``area_name`` or ``None`` if unknown.

    Lookups are case-insensitive, strip whitespace, and tolerate the common
    ``Throughout `` prefix used by the Charity Commission.
    """
    if not area_name:
        return None
    normalised = _normalise(area_name)
    if not normalised:
        return None
    return load_lookup_table().get(normalised)


def lookup_lad_centroid(area_name: str | None) -> tuple[float, float] | None:
    """Return ``(lat, lon)`` for ``area_name`` or ``None`` when not covered.

    Same normalisation as :func:`lookup_lad_code`. Coverage is sparse — only
    UK nations and major cities. Caller should treat ``None`` as 'fall back to
    something else' (or omit ``geolocation`` from the Murmurations envelope).
    """
    if not area_name:
        return None
    normalised = _normalise(area_name)
    if not normalised:
        return None
    return load_centroid_table().get(normalised)


def refresh_from_ons(
    *,
    http_client_factory: Callable[..., Any] | None = None,
    timeout: float = 30.0,
    page_size: int = 2000,
) -> int:
    """Refresh the on-disk lookup table from the ONS Open Geography Portal.

    Returns the number of LAD entries written (excluding the always-preserved
    UK nation codes). Raises :class:`OnsRefreshError` on transport or parsing
    failure — the on-disk file is left untouched in that case.

    ``http_client_factory`` is the callable used to construct the HTTP client;
    it defaults to :class:`httpx.Client`. Tests pass a fake to keep the call
    offline.
    """
    factory = http_client_factory or httpx.Client

    params = {
        "where": "1=1",
        "outFields": "LAD24NM,LAD24CD",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": page_size,
    }

    try:
        with factory(timeout=timeout) as client:
            response = client.get(_ONS_LAD_FEATURE_URL, params=params)
        if getattr(response, "status_code", 0) != 200:
            raise OnsRefreshError(
                f"ONS portal returned HTTP {getattr(response, 'status_code', '?')}"
            )
        payload = response.json()
    except OnsRefreshError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise OnsRefreshError(f"ONS refresh failed: {exc}") from exc

    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise OnsRefreshError("ONS response did not contain a 'features' list")

    new_entries: dict[str, str] = dict(_BASE_NATION_CODES)
    written = 0
    for feature in features:
        attrs = feature.get("attributes") if isinstance(feature, dict) else None
        if not isinstance(attrs, dict):
            continue
        name = attrs.get("LAD24NM")
        code = attrs.get("LAD24CD")
        if not name or not code:
            continue
        new_entries[str(name).lower()] = str(code)
        written += 1

    output = {
        "schema_version": "ons/refresh",
        "fetched_at": __import__("datetime").date.today().isoformat(),
        "source": _ONS_LAD_FEATURE_URL,
        "notes": (
            "Generated by refresh_from_ons. UK nation codes are always "
            "preserved alongside the upstream LAD entries."
        ),
        "entries": new_entries,
    }
    _LOOKUP_PATH.write_text(json.dumps(output, indent=2, sort_keys=True))
    _load_raw_data.cache_clear()
    load_lookup_table.cache_clear()
    load_centroid_table.cache_clear()
    return written


__all__ = [
    "OnsRefreshError",
    "load_centroid_table",
    "load_lookup_table",
    "lookup_lad_centroid",
    "lookup_lad_code",
    "refresh_from_ons",
]
