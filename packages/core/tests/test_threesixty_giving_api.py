"""Tests for the 360Giving API v1 enricher.

The new 360Giving REST API (2024) at api.threesixtygiving.org/api/v1/
allows querying by org_id directly — the same GB-CHC-{number} scheme
Open Org already uses. No auth required, 2 req/sec rate limit.

This is a new module alongside the existing threesixty_giving.py (which
uses the old bulk-file/registry pattern and is kept for the llmstxt-social
generator).

Tests mock all HTTP — no network access.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmstxt_core.enrichers.threesixty_giving_api import (
    GrantRecord,
    GrantSummary,
    fetch_grant_summary,
    fetch_grants_received,
    fetch_grants_made,
    grants_to_evidence,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_grant_summary_accepts_all_fields():
    s = GrantSummary(
        org_id="GB-CHC-1234567",
        is_funder=True,
        is_recipient=True,
        grants_received_count=15,
        grants_received_total=450000,
        grants_received_avg=30000,
        grants_received_min=5000,
        grants_received_max=80000,
        grants_made_count=42,
        grants_made_total=1200000,
        grants_made_avg=28571,
        grants_made_min=1000,
        grants_made_max=100000,
    )
    assert s.org_id == "GB-CHC-1234567"
    assert s.is_funder is True
    assert s.grants_received_total == 450000
    assert s.grants_made_count == 42


def test_grant_summary_optional_fields_default():
    s = GrantSummary(org_id="GB-CHC-1234567")
    assert s.is_funder is False
    assert s.is_recipient is False
    assert s.grants_received_count == 0
    assert s.grants_received_total == 0
    assert s.grants_made_count == 0
    assert s.grants_made_total == 0


def test_grant_record_has_required_fields():
    g = GrantRecord(
        grant_id="360G-abc123",
        title="Community food programme",
        description="3-year programme supporting food banks",
        amount=50000,
        currency="GBP",
        award_date="2024-01-15",
        funder_name="National Lottery Community Fund",
        funder_org_id="GB-CHC-1098765",
        recipient_name="Riverside Trust",
        recipient_org_id="GB-CHC-1234567",
        url="https://grantnav.threesixtygiving.org/grant/360G-abc123",
    )
    assert g.grant_id == "360G-abc123"
    assert g.amount == 50000
    assert g.currency == "GBP"


def test_grant_record_optional_fields_default():
    g = GrantRecord(
        grant_id="360G-xyz",
        title="Emergency food relief",
        description=None,
        amount=10000,
        currency="GBP",
        award_date="2023-06-01",
        funder_name="Some Funder",
        funder_org_id=None,
        recipient_name="Some Org",
        recipient_org_id=None,
        url=None,
    )
    assert g.description is None
    assert g.funder_org_id is None
    assert g.url is None


# ---------------------------------------------------------------------------
# API response fixtures
# ---------------------------------------------------------------------------

_ORG_SUMMARY_RESPONSE = {
    "id": "GB-CHC-1234567",
    "name": "Riverside Community Trust",
    "is_funder": True,
    "is_grant_recipient": True,
    "grants_received": {
        "count": 15,
        "amounts": {
            "total": 450000,
            "avg": 30000,
            "min": 5000,
            "max": 80000,
            "currencies": {"GBP": {"count": 15, "total": 450000}},
        },
    },
    "grants_made": {
        "count": 42,
        "amounts": {
            "total": 1200000,
            "avg": 28571,
            "min": 1000,
            "max": 100000,
            "currencies": {"GBP": {"count": 42, "total": 1200000}},
        },
    },
}

_ORG_SUMMARY_FUNDER_ONLY = {
    "id": "GB-CHC-1098765",
    "name": "National Lottery Community Fund",
    "is_funder": True,
    "is_grant_recipient": False,
    "grants_made": {
        "count": 500,
        "amounts": {
            "total": 25000000,
            "avg": 50000,
            "min": 500,
            "max": 500000,
            "currencies": {"GBP": {"count": 500, "total": 25000000}},
        },
    },
}

_ORG_SUMMARY_NOT_FOUND = {
    "id": "GB-CHC-9999999",
    "name": "",
    "is_funder": False,
    "is_grant_recipient": False,
}

_GRANTS_RECEIVED_RESPONSE = {
    "results": [
        {
            "id": "360G-abc123",
            "title": "Community food programme",
            "description": "3-year programme supporting food banks",
            "amountAwarded": 50000,
            "currency": "GBP",
            "awardDate": "2024-01-15T00:00:00",
            "fundingOrganization": [{"id": "GB-CHC-1098765", "name": "National Lottery Community Fund"}],
            "recipientOrganization": [{"id": "GB-CHC-1234567", "name": "Riverside Trust"}],
        },
        {
            "id": "360G-def456",
            "title": "Winter hardship fund",
            "description": "Emergency grants for families",
            "amountAwarded": 25000,
            "currency": "GBP",
            "awardDate": "2023-11-01T00:00:00",
            "fundingOrganization": [{"id": "GB-CHC-5550001", "name": "BBC Children in Need"}],
            "recipientOrganization": [{"id": "GB-CHC-1234567", "name": "Riverside Trust"}],
        },
    ],
    "next": None,
}

_GRANTS_MADE_RESPONSE = {
    "results": [
        {
            "id": "360G-ghi789",
            "title": "Small grants programme",
            "description": "Grants of £500-£5000 for local groups",
            "amountAwarded": 5000,
            "currency": "GBP",
            "awardDate": "2024-02-01T00:00:00",
            "fundingOrganization": [{"id": "GB-CHC-1234567", "name": "Riverside Trust"}],
            "recipientOrganization": [{"id": "GB-CHC-2222222", "name": "Southtown Food Bank"}],
        },
    ],
    "next": None,
}


def _mock_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# fetch_grant_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_grant_summary_returns_summary_on_200():
    resp = _mock_response(200, _ORG_SUMMARY_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-1234567")

    assert summary is not None
    assert summary.org_id == "GB-CHC-1234567"
    assert summary.is_funder is True
    assert summary.is_recipient is True
    assert summary.grants_received_count == 15
    assert summary.grants_received_total == 450000
    assert summary.grants_made_count == 42
    assert summary.grants_made_total == 1200000


@pytest.mark.asyncio
async def test_fetch_grant_summary_funder_only():
    """An org that only makes grants (not receives) still works."""
    resp = _mock_response(200, _ORG_SUMMARY_FUNDER_ONLY)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-1098765")

    assert summary is not None
    assert summary.is_funder is True
    assert summary.is_recipient is False
    assert summary.grants_received_count == 0
    assert summary.grants_made_count == 500


@pytest.mark.asyncio
async def test_fetch_grant_summary_returns_none_on_404():
    resp = _mock_response(404)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-9999999")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_returns_none_on_empty_name():
    """An API response with empty name means the org wasn't found."""
    resp = _mock_response(200, _ORG_SUMMARY_NOT_FOUND)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-9999999")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_handles_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-1234567")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_hits_correct_endpoint():
    resp = _mock_response(200, _ORG_SUMMARY_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        await fetch_grant_summary("GB-CHC-1234567")

    url = mock_client.get.call_args.args[0]
    assert "api.threesixtygiving.org" in url
    assert "/org/GB-CHC-1234567" in url


# ---------------------------------------------------------------------------
# fetch_grants_received / fetch_grants_made
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_grants_received_returns_grant_records():
    resp = _mock_response(200, _GRANTS_RECEIVED_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1234567")

    assert len(grants) == 2
    assert grants[0].grant_id == "360G-abc123"
    assert grants[0].title == "Community food programme"
    assert grants[0].amount == 50000
    assert grants[0].funder_name == "National Lottery Community Fund"
    assert grants[0].funder_org_id == "GB-CHC-1098765"
    assert grants[0].recipient_org_id == "GB-CHC-1234567"


@pytest.mark.asyncio
async def test_fetch_grants_made_returns_grant_records():
    resp = _mock_response(200, _GRANTS_MADE_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_made("GB-CHC-1234567")

    assert len(grants) == 1
    assert grants[0].grant_id == "360G-ghi789"
    assert grants[0].amount == 5000
    assert grants[0].recipient_name == "Southtown Food Bank"


@pytest.mark.asyncio
async def test_fetch_grants_received_empty_results():
    resp = _mock_response(200, {"results": [], "next": None})
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1234567")

    assert grants == []


@pytest.mark.asyncio
async def test_fetch_grants_received_handles_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1234567")

    assert grants == []


@pytest.mark.asyncio
async def test_fetch_grants_received_strips_time_from_award_date():
    """Award dates come as ISO datetime; we keep the date part only."""
    resp = _mock_response(200, _GRANTS_RECEIVED_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1234567")

    assert grants[0].award_date == "2024-01-15"


# ---------------------------------------------------------------------------
# grants_to_evidence — maps grants to evidence[] items
# ---------------------------------------------------------------------------


def test_grants_to_evidence_maps_grant_to_outcome_data():
    grants = [
        GrantRecord(
            grant_id="360G-abc123",
            title="Community food programme",
            description="3-year programme supporting food banks",
            amount=50000,
            currency="GBP",
            award_date="2024-01-15",
            funder_name="National Lottery Community Fund",
            funder_org_id="GB-CHC-1098765",
            recipient_name="Riverside Trust",
            recipient_org_id="GB-CHC-1234567",
            url="https://grantnav.threesixtygiving.org/grant/360G-abc123",
        ),
    ]
    items = grants_to_evidence(grants)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "outcome_data"
    assert "food" in item["title"].lower()
    assert item["date"] == "2024-01-15"
    assert item["url"] is not None
    assert "360G-abc123" in item["url"]


def test_grants_to_evidence_empty_list():
    assert grants_to_evidence([]) == []


def test_grants_to_evidence_generates_unique_ids():
    grants = [
        GrantRecord(
            grant_id="360G-a",
            title="Grant A",
            description="desc",
            amount=10000,
            currency="GBP",
            award_date="2024-01-01",
            funder_name="Funder",
            funder_org_id=None,
            recipient_name="Org",
            recipient_org_id=None,
            url=None,
        ),
        GrantRecord(
            grant_id="360G-b",
            title="Grant B",
            description="desc",
            amount=20000,
            currency="GBP",
            award_date="2024-02-01",
            funder_name="Funder",
            funder_org_id=None,
            recipient_name="Org",
            recipient_org_id=None,
            url=None,
        ),
    ]
    items = grants_to_evidence(grants)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)


def test_grants_to_evidence_includes_funder_in_outcomes():
    grants = [
        GrantRecord(
            grant_id="360G-x",
            title="Test grant",
            description="desc",
            amount=30000,
            currency="GBP",
            award_date="2024-03-01",
            funder_name="Big Funder",
            funder_org_id="GB-CHC-999",
            recipient_name="Test Org",
            recipient_org_id="GB-CHC-111",
            url=None,
        ),
    ]
    items = grants_to_evidence(grants)
    assert len(items[0]["outcomes"]) > 0
    outcome = items[0]["outcomes"][0]
    assert "funder" in outcome["description"].lower() or "Big Funder" in outcome["description"]