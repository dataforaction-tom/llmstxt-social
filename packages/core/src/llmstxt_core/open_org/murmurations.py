"""Murmurations envelope builder + index client.

Two layers:

* :func:`build_envelope` — turn a stored Open Org ``profile_json`` into the
  flat shape the Murmurations index validates against
  ``open_org_profile-v0.1.0``. Pure-ish: geolocation lookups are injected.
* :class:`MurmurationsClient` — thin async wrapper around the Murmurations
  index REST API. All HTTP is injectable for tests.

The Murmurations submit/validate endpoints accept a *URL* (not a body) —
they fetch and validate. So the envelope must be served at a stable public
URL (see ``routes/open_org_public.py``); this module just produces it and
relays the URL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx


MURMURATIONS_SCHEMA_NAME = "open_org_profile-v0.1.0"
DEFAULT_TEST_INDEX_URL = "https://test-index.murmurations.network/v2"
DEFAULT_TEST_LIBRARY_URL = "https://test-library.murmurations.network/v2"


# ---------------------------------------------------------------------------
# Envelope builder
# ---------------------------------------------------------------------------


PostcodeLookup = Callable[..., Awaitable[tuple[float, float] | None]]
CentroidLookup = Callable[[str | None], tuple[float, float] | None]


async def build_envelope(
    profile_json: dict,
    *,
    frontend_base_url: str,
    postcodes_io_lookup: PostcodeLookup,
    ons_centroid_lookup: CentroidLookup,
    strategy_themes: list[str] | None = None,
    ideas_count: int = 0,
) -> dict:
    """Build the flat Murmurations envelope for a stored Open Org profile.

    Geolocation chain: profile-embedded > postcodes.io(postcode) > LAD centroid
    by primary area > omit.
    """
    identity = profile_json.get("identity", {}) or {}
    mission = profile_json.get("mission", {}) or {}

    org_id = (identity.get("identifiers") or {}).get("org_id") or ""
    base = frontend_base_url.rstrip("/")
    open_org_profile_url = f"{base}/open-org/{org_id}/profile.json"

    primary_url = identity.get("website") or open_org_profile_url

    geolocation = await _resolve_geolocation(
        profile_json,
        postcodes_io_lookup=postcodes_io_lookup,
        ons_centroid_lookup=ons_centroid_lookup,
    )

    envelope: dict[str, Any] = {
        "linked_schemas": [MURMURATIONS_SCHEMA_NAME],
        "name": identity.get("name"),
        "primary_url": primary_url,
        "org_id_guide": org_id,
        "tags": list(mission.get("themes") or []),
        "schema_version": profile_json.get("schema_version", "open-org/v0.1"),
        "open_org_profile_url": open_org_profile_url,
    }
    if geolocation is not None:
        envelope["geolocation"] = {"lat": geolocation[0], "lon": geolocation[1]}

    registration = identity.get("registration") or {}
    if registration:
        envelope["registration"] = {
            k: v for k, v in registration.items() if isinstance(v, str)
        }

    geography = identity.get("geography") or {}
    if geography.get("primary_area"):
        envelope["primary_area"] = geography["primary_area"]
    if geography.get("primary_area_code"):
        envelope["primary_area_code"] = geography["primary_area_code"]

    scale = identity.get("scale") or {}
    if scale.get("annual_income_band"):
        envelope["annual_income_band"] = scale["annual_income_band"]

    if strategy_themes:
        envelope["strategy_themes"] = list(strategy_themes)
    if ideas_count:
        envelope["ideas_count"] = int(ideas_count)

    return envelope


async def _resolve_geolocation(
    profile_json: dict,
    *,
    postcodes_io_lookup: PostcodeLookup,
    ons_centroid_lookup: CentroidLookup,
) -> tuple[float, float] | None:
    geography = (profile_json.get("identity") or {}).get("geography") or {}
    existing = geography.get("geolocation")
    if isinstance(existing, dict):
        lat = existing.get("lat")
        lon = existing.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)

    contact = (profile_json.get("identity") or {}).get("contact") or {}
    postcode = contact.get("postcode")
    if postcode:
        try:
            located = await postcodes_io_lookup(postcode)
        except Exception:  # noqa: BLE001
            # Network/transient failures fall through to centroid — the
            # envelope can still go out, just less precisely located.
            located = None
        if located is not None:
            return located

    primary_area = geography.get("primary_area")
    if primary_area:
        centroid = ons_centroid_lookup(primary_area)
        if centroid is not None:
            return centroid

    return None


# ---------------------------------------------------------------------------
# Index client
# ---------------------------------------------------------------------------


class MurmurationsError(RuntimeError):
    """Raised for transient (5xx) or unparseable responses from the index."""


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class SubmissionResult:
    node_id: str
    status: str


class MurmurationsClient:
    """Async client for the Murmurations index REST API.

    ``index_url`` should include the API version prefix
    (e.g. ``https://test-index.murmurations.network/v2``). HTTP client factory
    is injectable for tests; production callers default to :class:`httpx.AsyncClient`.
    """

    def __init__(
        self,
        *,
        index_url: str,
        library_url: str,
        http_client_factory: Callable[..., Any] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._index_url = index_url.rstrip("/")
        self._library_url = library_url.rstrip("/")
        self._factory = http_client_factory or httpx.AsyncClient
        self._timeout = timeout

    @property
    def index_url(self) -> str:
        return self._index_url

    async def validate_profile(self, profile_url: str) -> ValidationResult:
        async with self._factory(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._index_url}/validate", json={"profile_url": profile_url}
            )

        status = getattr(response, "status_code", 0)
        if status == 200:
            return ValidationResult(valid=True)
        if 400 <= status < 500:
            payload = _safe_json(response)
            errors = _extract_error_messages(payload)
            return ValidationResult(valid=False, errors=errors)
        raise MurmurationsError(
            f"Murmurations validate returned HTTP {status}: {getattr(response, 'text', '')}"
        )

    async def submit_node(self, profile_url: str) -> SubmissionResult:
        async with self._factory(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._index_url}/nodes", json={"profile_url": profile_url}
            )

        status = getattr(response, "status_code", 0)
        if status >= 500:
            raise MurmurationsError(
                f"Murmurations submit returned HTTP {status}: {getattr(response, 'text', '')}"
            )
        payload = _safe_json(response)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise MurmurationsError(
                f"Murmurations submit returned unexpected payload: {payload!r}"
            )
        node_id = data.get("node_id") or ""
        status_str = data.get("status") or "unknown"
        return SubmissionResult(node_id=str(node_id), status=str(status_str))

    async def fetch_nodes_by_schema(
        self, schema_name: str, *, page_size: int = 100
    ) -> list[dict]:
        """Return all node entries matching ``schema_name``.

        The index paginates; this iterates pages until exhausted. Errors raise.
        """
        nodes: list[dict] = []
        page = 1
        while True:
            async with self._factory(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._index_url}/nodes",
                    params={
                        "schema": schema_name,
                        "page": page,
                        "page_size": page_size,
                    },
                )
            status = getattr(response, "status_code", 0)
            if status >= 500:
                raise MurmurationsError(
                    f"Murmurations fetch returned HTTP {status}"
                )
            payload = _safe_json(response)
            page_data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(page_data, list):
                break
            nodes.extend(page_data)
            meta = payload.get("meta") if isinstance(payload, dict) else {}
            total_pages = meta.get("total_pages") if isinstance(meta, dict) else 1
            if page >= (total_pages or 1) or not page_data:
                break
            page += 1
        return nodes

    async def delete_node(self, node_id: str) -> None:
        async with self._factory(timeout=self._timeout) as client:
            response = await client.delete(f"{self._index_url}/nodes/{node_id}")
        status = getattr(response, "status_code", 0)
        if status >= 500:
            raise MurmurationsError(
                f"Murmurations delete returned HTTP {status}"
            )


def _safe_json(response: Any) -> dict | list:
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return {}


def _extract_error_messages(payload: dict | list) -> list[str]:
    """Surface human-readable error strings from a Murmurations error payload."""
    if not isinstance(payload, dict):
        return []
    errors = payload.get("errors")
    if isinstance(errors, list):
        out: list[str] = []
        for e in errors:
            if isinstance(e, dict):
                msg = e.get("detail") or e.get("title") or ""
                if msg:
                    out.append(str(msg))
            elif isinstance(e, str):
                out.append(e)
        return out
    detail = payload.get("error") or payload.get("message")
    if isinstance(detail, str):
        return [detail]
    return []


__all__ = [
    "DEFAULT_TEST_INDEX_URL",
    "DEFAULT_TEST_LIBRARY_URL",
    "MURMURATIONS_SCHEMA_NAME",
    "MurmurationsClient",
    "MurmurationsError",
    "SubmissionResult",
    "ValidationResult",
    "build_envelope",
]
