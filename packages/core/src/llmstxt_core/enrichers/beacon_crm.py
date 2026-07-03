"""Beacon CRM enricher (Pattern A — read-only enrichment).

Reads constituent, donation, and case-management data from Beacon CRM's
REST API and maps donations + cases to Open Org ``evidence[]`` items.

Beacon API:
    - Auth: ``Authorization: Bearer {api_key}`` header
    - Base URL: ``https://api.beaconcrm.org/api/v1``
    - Pagination: ``page`` + ``per_page`` params; response has
      ``data`` array + ``meta`` pagination object.

Endpoints used:
    GET /constituents          — search constituents
    GET /constituents/{id}     — constituent detail
    GET /constituents/{id}/donations — donation history
    GET /constituents/{id}/cases     — case management records

This is Pattern A (read-only) — no writes to Beacon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


_DEFAULT_BASE_URL = "https://api.beaconcrm.org/api/v1"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BeaconConstituent:
    """A Beacon CRM constituent (donor, supporter, or organisation)."""

    id: str
    name: str
    email: str | None = None
    type: str | None = None
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class BeaconDonation:
    """A single donation recorded against a constituent."""

    id: str
    amount: int
    currency: str
    date: str
    fund: str | None = None
    campaign: str | None = None


@dataclass
class BeaconCase:
    """A case-management record attached to a constituent."""

    id: str
    title: str
    status: str
    opened_date: str | None = None
    closed_date: str | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class BeaconClient:
    """Async client for the Beacon CRM REST API (read-only).

    Args:
        api_key: Beacon API key (sent as ``Bearer {api_key}``).
        base_url: API base URL. Defaults to the production endpoint.
        http_client_factory: Zero-arg callable returning an async-context
            manager (e.g. ``httpx.AsyncClient``). Injected for testing; in
            production this defaults to a configured ``httpx.AsyncClient``.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        http_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        if http_client_factory is None:
            def _default_factory() -> httpx.AsyncClient:
                return httpx.AsyncClient(timeout=15)
            http_client_factory = _default_factory
        self._http_client_factory = http_client_factory

    # -- public API -------------------------------------------------------

    async def get_constituent(self, constituent_id: str) -> BeaconConstituent | None:
        """Fetch a single constituent by ID. Returns ``None`` on 404/error."""
        data = await self._get(f"/constituents/{constituent_id}")
        if data is None:
            return None
        return _parse_constituent(data)

    async def search_constituents(self, query: str, limit: int = 20) -> list[BeaconConstituent]:
        """Search constituents by free-text query.

        Returns a list (empty on error or no matches).
        """
        data = await self._get(
            "/constituents",
            params={"q": query, "per_page": limit},
        )
        if data is None:
            return []
        return [_parse_constituent(row) for row in data.get("data", [])]

    async def get_donations(self, constituent_id: str) -> list[BeaconDonation]:
        """Fetch donation history for a constituent. Empty list on error."""
        data = await self._get(f"/constituents/{constituent_id}/donations")
        if data is None:
            return []
        return [_parse_donation(row) for row in data.get("data", [])]

    async def get_cases(self, constituent_id: str) -> list[BeaconCase]:
        """Fetch case-management records for a constituent. Empty list on error."""
        data = await self._get(f"/constituents/{constituent_id}/cases")
        if data is None:
            return []
        return [_parse_case(row) for row in data.get("data", [])]

    # -- write API (Pattern B — push) -------------------------------------

    async def create_constituent(self, payload: dict) -> dict:
        """Create a constituent via POST /constituents.

        Returns the parsed JSON body (containing the new ``id``).
        Raises ``httpx.HTTPStatusError`` on non-2xx responses.
        """
        return await self._post("/constituents", json_body=payload)

    async def create_campaign(self, constituent_id: str, payload: dict) -> dict:
        """Create a campaign attached to ``constituent_id``.

        POST /constituents/{id}/campaigns — returns parsed JSON with the
        new campaign ``id``.
        """
        return await self._post(
            f"/constituents/{constituent_id}/campaigns", json_body=payload
        )

    # -- internals --------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict | None:
        """Perform a GET request and return the parsed JSON body.

        Returns ``None`` on 404 or network error so callers can decide
        the appropriate empty sentinel (``None`` vs ``[]``).
        """
        url = f"{self.base_url}{path}"
        try:
            async with self._http_client_factory() as client:
                resp = await client.get(url, params=params, headers=self._headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, KeyError, ValueError):
            return None

    async def _post(self, path: str, json_body: dict) -> dict:
        """Perform a POST request and return the parsed JSON body.

        Raises ``httpx.HTTPStatusError`` on non-2xx so callers can handle
        write failures explicitly (Pattern B — writes should not silently
        swallow errors the way reads do).
        """
        url = f"{self.base_url}{path}"
        async with self._http_client_factory() as client:
            resp = await client.post(url, json=json_body, headers=self._headers)
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_constituent(raw: dict) -> BeaconConstituent:
    return BeaconConstituent(
        id=raw.get("id") or "",
        name=raw.get("name") or "",
        email=raw.get("email"),
        type=raw.get("type"),
        tags=list(raw.get("tags") or []),
        custom_fields=dict(raw.get("custom_fields") or {}),
    )


def _parse_donation(raw: dict) -> BeaconDonation:
    return BeaconDonation(
        id=raw.get("id") or "",
        amount=raw.get("amount") or 0,
        currency=raw.get("currency") or "GBP",
        date=raw.get("date") or "",
        fund=raw.get("fund"),
        campaign=raw.get("campaign"),
    )


def _parse_case(raw: dict) -> BeaconCase:
    return BeaconCase(
        id=raw.get("id") or "",
        title=raw.get("title") or "",
        status=raw.get("status") or "",
        opened_date=raw.get("opened_date"),
        closed_date=raw.get("closed_date"),
        description=raw.get("description"),
    )


# ---------------------------------------------------------------------------
# Evidence mappers
# ---------------------------------------------------------------------------


def donations_to_evidence(donations: list[BeaconDonation]) -> list[dict]:
    """Map donations to ``evidence[]`` items (evidence_type: ``outcome_data``).

    Each donation becomes an evidence item with an ``outcomes`` array
    capturing the amount, currency, fund, and campaign.
    """
    items: list[dict] = []
    for i, d in enumerate(donations):
        outcomes = [
            {
                "metric": "donation_amount",
                "value": d.amount,
                "currency": d.currency,
                "description": _donation_outcome_description(d),
            }
        ]
        items.append(
            {
                "evidence_id": f"beacon-donation-{i + 1}",
                "title": _donation_title(d),
                "evidence_type": "outcome_data",
                "date": d.date,
                "url": None,
                "themes": [],
                "outcomes": outcomes,
            }
        )
    return items


def cases_to_evidence(cases: list[BeaconCase]) -> list[dict]:
    """Map cases to ``evidence[]`` items (evidence_type: ``case_study``).

    Each case-management record becomes a case-study evidence item.
    """
    items: list[dict] = []
    for i, c in enumerate(cases):
        items.append(
            {
                "evidence_id": f"beacon-case-{i + 1}",
                "title": c.title,
                "evidence_type": "case_study",
                "date": c.opened_date or "",
                "url": None,
                "themes": [],
                "description": c.description or "",
                "outcomes": [],
            }
        )
    return items


def _donation_title(d: BeaconDonation) -> str:
    parts = [p for p in (d.campaign, d.fund) if p]
    if parts:
        return " — ".join(parts)
    return f"Donation {d.id}"


def _donation_outcome_description(d: BeaconDonation) -> str:
    bits = [f"{d.amount:,} {d.currency}"]
    if d.fund:
        bits.append(f"fund: {d.fund}")
    if d.campaign:
        bits.append(f"campaign: {d.campaign}")
    return "Donation of " + ", ".join(bits)