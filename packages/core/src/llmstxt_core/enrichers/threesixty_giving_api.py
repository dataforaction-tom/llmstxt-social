"""Fetch grant data from the 360Giving REST API v1.

The 360Giving REST API at api.threesixtygiving.org/api/v1/ allows
querying by org_id directly — the same GB-CHC-{number} scheme Open Org
already uses. No auth required, 2 req/sec rate limit.

Endpoints:
    GET /org/{org_id}/               — aggregate stats (funder/recipient)
    GET /org/{org_id}/grants_made/   — paginated grants this org awarded
    GET /org/{org_id}/grants_received/ — paginated grants this org received

Real API response shapes (captured July 2026):

/org/{org_id}/  →  {
    "funder": null | {"aggregate": {"grants": N, ..., "currencies": {"GBP": {"avg", "max", "min", "total", "grants"}}}},
    "recipient": null | {"aggregate": { ... same shape ... }},
    "name": "...",
    "org_id": "GB-CHC-...",
    ...
}
404 → {"detail": "Not found."}

/org/{org_id}/grants_{received,made}/  →  {
    "count": N,
    "next": url | null,
    "previous": url | null,
    "results": [
        {
            "grant_id": "360G-...",
            "data": {
                "id": "360G-...",
                "title": "...",
                "amountAwarded": 50000,
                "currency": "GBP",
                "awardDate": "2024-01-15T00:00:00+00:00",
                "description": "...",
                "fundingOrganization": [{"id": "GB-CHC-...", "name": "..."}],
                "recipientOrganization": [{"id": "GB-CHC-...", "name": "..."}],
            },
            ...
        }
    ]
}

Key difference from the imagined shape: grant fields are nested under
result["data"], not at the top level. The summary uses "funder"/"recipient"
keys (null when absent) with "aggregate.currencies.GBP" sub-objects,
not "grants_received"/"grants_made" with "amounts".

This is a new module alongside the existing threesixty_giving.py (which
uses the old bulk-file/registry pattern and is kept for backward compat).
"""

from dataclasses import dataclass

import httpx


_BASE_URL = "https://api.threesixtygiving.org/api/v1"
_GRANTNAV_URL = "https://grantnav.threesixtygiving.org/grant"


@dataclass
class GrantSummary:
    """Aggregate grant statistics for an organisation."""

    org_id: str
    is_funder: bool = False
    is_recipient: bool = False
    grants_received_count: int = 0
    grants_received_total: float = 0
    grants_received_avg: float = 0
    grants_received_min: float = 0
    grants_received_max: float = 0
    grants_made_count: int = 0
    grants_made_total: float = 0
    grants_made_avg: float = 0
    grants_made_min: float = 0
    grants_made_max: float = 0


@dataclass
class GrantRecord:
    """A single grant from the 360Giving API."""

    grant_id: str
    title: str
    description: str | None
    amount: float
    currency: str
    award_date: str
    funder_name: str
    funder_org_id: str | None
    recipient_name: str
    recipient_org_id: str | None
    url: str | None = None


async def fetch_grant_summary(org_id: str) -> GrantSummary | None:
    """Fetch aggregate grant statistics for an organisation.

    Args:
        org_id: Organisation ID in org-id.guide format (e.g. "GB-CHC-1234567").

    Returns:
        ``GrantSummary`` if the org has grant data, ``None`` if not found,
        no grants, or network error.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_BASE_URL}/org/{org_id}/")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            # 404 body is {"detail": "Not found."} — double-check
            if data.get("detail"):
                return None

            # Empty name means the org wasn't found
            if not data.get("name"):
                return None

            return _parse_summary(data, org_id)
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


def _parse_summary(data: dict, org_id: str) -> GrantSummary | None:
    """Parse the /org/{org_id}/ response into a GrantSummary.

    Real shape:
        funder: null | {aggregate: {grants: N, currencies: {GBP: {avg, max, min, total, grants}}}}
        recipient: null | {aggregate: { ... same ... }}
    """
    funder = data.get("funder")
    recipient = data.get("recipient")

    # If neither funder nor recipient data exists, the org has no grants
    if not funder and not recipient:
        return None

    funder_agg = (funder or {}).get("aggregate", {})
    recipient_agg = (recipient or {}).get("aggregate", {})

    funder_currencies = funder_agg.get("currencies", {})
    recipient_currencies = recipient_agg.get("currencies", {})

    # Use GBP as the primary currency (the API reports per-currency)
    funder_gbp = funder_currencies.get("GBP", {})
    recipient_gbp = recipient_currencies.get("GBP", {})

    return GrantSummary(
        org_id=org_id,
        is_funder=bool(funder),
        is_recipient=bool(recipient),
        grants_received_count=recipient_agg.get("grants", 0),
        grants_received_total=recipient_gbp.get("total", 0),
        grants_received_avg=recipient_gbp.get("avg", 0),
        grants_received_min=recipient_gbp.get("min", 0),
        grants_received_max=recipient_gbp.get("max", 0),
        grants_made_count=funder_agg.get("grants", 0),
        grants_made_total=funder_gbp.get("total", 0),
        grants_made_avg=funder_gbp.get("avg", 0),
        grants_made_min=funder_gbp.get("min", 0),
        grants_made_max=funder_gbp.get("max", 0),
    )


async def fetch_grants_received(org_id: str, limit: int = 50) -> list[GrantRecord]:
    """Fetch grants received by an organisation.

    Args:
        org_id: Organisation ID (e.g. "GB-CHC-1234567").
        limit: Maximum number of grants to return.

    Returns:
        List of ``GrantRecord``, empty list on error or no grants.
    """
    return await _fetch_grants(org_id, "grants_received", limit)


async def fetch_grants_made(org_id: str, limit: int = 50) -> list[GrantRecord]:
    """Fetch grants made (awarded) by an organisation.

    Args:
        org_id: Organisation ID (e.g. "GB-CHC-1234567").
        limit: Maximum number of grants to return.

    Returns:
        List of ``GrantRecord``, empty list on error or no grants.
    """
    return await _fetch_grants(org_id, "grants_made", limit)


async def _fetch_grants(org_id: str, endpoint: str, limit: int) -> list[GrantRecord]:
    """Fetch and parse grants from a paginated endpoint.

    Real response shape:
        {
            "count": N,
            "next": url | null,
            "results": [
                {
                    "grant_id": "360G-...",
                    "data": {  # ← grant fields are under "data", not top-level
                        "id": "360G-...",
                        "title": "...",
                        "amountAwarded": 50000,
                        ...
                    }
                }
            ]
        }
    """
    grants: list[GrantRecord] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url: str | None = f"{_BASE_URL}/org/{org_id}/{endpoint}/?page_size={limit}"
            while url and len(grants) < limit:
                resp = await client.get(url)
                if resp.status_code != 200:
                    break
                data = resp.json()
                for raw in data.get("results", []):
                    grant = _parse_grant(raw)
                    if grant:
                        grants.append(grant)
                        if len(grants) >= limit:
                            break
                url = data.get("next")
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        pass
    return grants


def _parse_grant(raw: dict) -> GrantRecord | None:
    """Parse a single grant result from the API response.

    The grant fields (id, title, amountAwarded, etc.) are nested under
    raw["data"], not at the top level. If "data" is None or missing,
    skip the record.
    """
    data = raw.get("data")
    if not data or not isinstance(data, dict):
        return None

    funder_orgs = data.get("fundingOrganization") or []
    recipient_orgs = data.get("recipientOrganization") or []
    funder = funder_orgs[0] if funder_orgs else {}
    recipient = recipient_orgs[0] if recipient_orgs else {}

    award_date_raw = data.get("awardDate") or ""
    # Strip time portion from ISO datetime (2024-01-15T00:00:00+00:00 → 2024-01-15)
    award_date = award_date_raw.split("T")[0] if award_date_raw else ""

    grant_id = data.get("id") or raw.get("grant_id") or ""
    url = f"{_GRANTNAV_URL}/{grant_id}" if grant_id else None

    return GrantRecord(
        grant_id=grant_id,
        title=data.get("title") or "",
        description=data.get("description"),
        amount=data.get("amountAwarded") or 0,
        currency=data.get("currency") or "GBP",
        award_date=award_date,
        funder_name=funder.get("name") or "",
        funder_org_id=funder.get("id"),
        recipient_name=recipient.get("name") or "",
        recipient_org_id=recipient.get("id"),
        url=url,
    )


def grants_to_evidence(grants: list[GrantRecord]) -> list[dict]:
    """Map grant records to evidence[] items for the Open Org profile.

    Each grant becomes an ``outcome_data`` evidence item, citing the
    GrantNav URL and including funder/amount in the outcomes.
    """
    items = []
    for i, g in enumerate(grants):
        outcomes = [
            {
                "metric": "grant_amount",
                "value": g.amount,
                "currency": g.currency,
                "description": f"Funded by {g.funder_name} (£{g.amount:,} {g.currency})",
            }
        ]
        items.append(
            {
                "evidence_id": f"360g-grant-{i + 1}",
                "title": g.title,
                "evidence_type": "outcome_data",
                "date": g.award_date,
                "url": g.url,
                "themes": [],
                "outcomes": outcomes,
            }
        )
    return items