"""Fetch grant data from the 360Giving REST API v1.

The new 360Giving API (2024) at api.threesixtygiving.org/api/v1/ allows
querying by org_id directly — the same GB-CHC-{number} scheme Open Org
already uses. No auth required, 2 req/sec rate limit.

Endpoints:
    GET /org/{org_id}/               — aggregate stats (funder/recipient)
    GET /org/{org_id}/grants_made/   — paginated grants this org awarded
    GET /org/{org_id}/grants_received/ — paginated grants this org received

This is a new module alongside the existing threesixty_giving.py (which
uses the old bulk-file/registry pattern and is kept for backward compat).
"""

from dataclasses import dataclass, field

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
    grants_received_total: int = 0
    grants_received_avg: float = 0
    grants_received_min: int = 0
    grants_received_max: int = 0
    grants_made_count: int = 0
    grants_made_total: int = 0
    grants_made_avg: float = 0
    grants_made_min: int = 0
    grants_made_max: int = 0


@dataclass
class GrantRecord:
    """A single grant from the 360Giving API."""

    grant_id: str
    title: str
    description: str | None
    amount: int
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
        ``GrantSummary`` if found, ``None`` if not found or network error.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_BASE_URL}/org/{org_id}/")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            # Empty name means the org wasn't found
            if not data.get("name"):
                return None

            return _parse_summary(data, org_id)
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def _parse_summary(data: dict, org_id: str) -> GrantSummary:
    """Parse the /org/{org_id}/ response into a GrantSummary."""
    received = data.get("grants_received") or {}
    received_amounts = received.get("amounts") or {}
    made = data.get("grants_made") or {}
    made_amounts = made.get("amounts") or {}

    return GrantSummary(
        org_id=org_id,
        is_funder=bool(data.get("is_funder")),
        is_recipient=bool(data.get("is_grant_recipient")),
        grants_received_count=received.get("count", 0),
        grants_received_total=received_amounts.get("total", 0),
        grants_received_avg=received_amounts.get("avg", 0),
        grants_received_min=received_amounts.get("min", 0),
        grants_received_max=received_amounts.get("max", 0),
        grants_made_count=made.get("count", 0),
        grants_made_total=made_amounts.get("total", 0),
        grants_made_avg=made_amounts.get("avg", 0),
        grants_made_min=made_amounts.get("min", 0),
        grants_made_max=made_amounts.get("max", 0),
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
    """Fetch and parse grants from a paginated endpoint."""
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
                    grants.append(_parse_grant(raw))
                    if len(grants) >= limit:
                        break
                url = data.get("next")
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    return grants


def _parse_grant(raw: dict) -> GrantRecord:
    """Parse a single grant record from the API response."""
    funder_orgs = raw.get("fundingOrganization") or []
    recipient_orgs = raw.get("recipientOrganization") or []
    funder = funder_orgs[0] if funder_orgs else {}
    recipient = recipient_orgs[0] if recipient_orgs else {}

    award_date_raw = raw.get("awardDate") or ""
    # Strip time portion from ISO datetime (2024-01-15T00:00:00 → 2024-01-15)
    award_date = award_date_raw.split("T")[0] if award_date_raw else ""

    grant_id = raw.get("id") or ""
    url = f"{_GRANTNAV_URL}/{grant_id}" if grant_id else None

    return GrantRecord(
        grant_id=grant_id,
        title=raw.get("title") or "",
        description=raw.get("description"),
        amount=raw.get("amountAwarded") or 0,
        currency=raw.get("currency") or "GBP",
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