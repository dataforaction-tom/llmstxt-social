"""postcodes.io UK postcode → lat/lon enricher.

Used by the Murmurations envelope builder: the index requires a ``geolocation``
field for search-by-place; Charity Commission data doesn't carry coordinates,
but it does carry postcodes. postcodes.io is a free public API maintained by
mySociety — no key, no quota in practice for our volume.

Returns ``None`` for unknown postcodes; raises :class:`PostcodesIoError` on
upstream 5xx so the caller (a Celery task) can decide whether to retry.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote

import httpx


_BASE_URL = "https://api.postcodes.io/postcodes"


class PostcodesIoError(RuntimeError):
    """Raised when postcodes.io returns a 5xx or otherwise unparseable response."""


async def lookup_geolocation(
    postcode: str | None,
    *,
    http_client_factory: Callable[..., Any] | None = None,
    timeout: float = 5.0,
) -> tuple[float, float] | None:
    """Return ``(lat, lon)`` for a UK postcode, or ``None`` if unknown.

    Postcodes are normalised (uppercase, trimmed) before the lookup.
    """
    if not postcode or not postcode.strip():
        return None

    normalised = postcode.strip().upper()
    url = f"{_BASE_URL}/{quote(normalised, safe='')}"

    factory = http_client_factory or httpx.AsyncClient
    async with factory(timeout=timeout) as client:
        response = await client.get(url)

    status = getattr(response, "status_code", 0)
    if status == 404:
        return None
    if status >= 500:
        raise PostcodesIoError(f"postcodes.io returned HTTP {status}")
    if status != 200:
        # Unexpected 4xx (invalid format, etc.) — treat as not-found.
        return None

    try:
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise PostcodesIoError(f"postcodes.io response was not JSON: {exc}") from exc

    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return None

    lat = result.get("latitude")
    lon = result.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None

    return float(lat), float(lon)


__all__ = ["PostcodesIoError", "lookup_geolocation"]
