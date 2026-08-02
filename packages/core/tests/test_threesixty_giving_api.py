"""Tests for the 360Giving API v1 enricher.

The 360Giving REST API at api.threesixtygiving.org/api/v1/ allows
querying by org_id directly — the same GB-CHC-{number} scheme Open Org
already uses. No auth required, 2 req/sec rate limit.

Tests mock all HTTP — no network access. Fixture shapes are captured from
the real API (July 2026) so mocks faithfully represent what the parser must
handle.

API response shapes (real, captured live):

/org/{org_id}/  →  {
    "self": "...",
    "grants_made": ".../grants_made/",
    "grants_received": ".../grants_received/",
    "funder": null | {
        "aggregate": {
            "grants": int,
            "earliest_grant_date": "YYYY-MM-DD",
            "latest_grant_date": "YYYY-MM-DD",
            "currencies": {
                "GBP": {"avg": float, "max": float, "min": float, "total": float, "grants": int}
            }
        }
    },
    "recipient": null | {  # same shape as funder
        "aggregate": { ... }
    },
    "publisher": null | {"prefix": "360G-..."},
    "org_id": "GB-CHC-...",
    "name": "...",
    "linked_orgs": [{"org_id": "GB-COH-..."}]
}

/org/{org_id}/grants_received/?page_size=N  →  {
    "count": int,
    "next": url | null,
    "previous": url | null,
    "results": [
        {
            "grant_id": "360G-...",
            "data": {
                "id": "360G-...",
                "title": "...",
                "currency": "GBP",
                "awardDate": "2024-01-15T00:00:00+00:00",
                "description": "...",
                "amountAwarded": 50000,
                "fundingOrganization": [{"id": "GB-CHC-...", "name": "..."}],
                "recipientOrganization": [{"id": "GB-CHC-...", "name": "..."}],
            },
            "data_license": {"url": "...", "name": "..."},
            "publisher": {"self": "...", "org_id": "..."},
            "recipients": [{"self": "...", "org_id": "..."}],
            "funders": [{"self": "...", "org_id": "..."}]
        },
        ...
    ]
}

Same shape for /grants_made/.
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
# API response fixtures (captured from real API, July 2026)
# ---------------------------------------------------------------------------

# Trussell Trust — real org that is both funder and recipient
_ORG_SUMMARY_RESPONSE = {
    "self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/",
    "grants_made": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/grants_made/",
    "grants_received": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/grants_received/",
    "funder": {
        "aggregate": {
            "grants": 2326,
            "earliest_grant_date": "2018-04-01",
            "latest_grant_date": "2025-05-16",
            "currencies": {
                "GBP": {
                    "avg": 38418.26,
                    "max": 659184.62,
                    "min": 25.0,
                    "total": 89360877.93,
                    "grants": 2326,
                }
            },
        }
    },
    "recipient": {
        "aggregate": {
            "grants": 79,
            "earliest_grant_date": "2010-11-11",
            "latest_grant_date": "2026-02-26",
            "currencies": {
                "GBP": {
                    "avg": 308627.06,
                    "max": 3500000.0,
                    "min": 160.0,
                    "total": 24381537.93,
                    "grants": 79,
                }
            },
        }
    },
    "publisher": {"prefix": "360G-TrussellTrust"},
    "org_id": "GB-CHC-1110522",
    "name": "Trussell",
    "linked_orgs": [{"org_id": "GB-COH-05434524"}],
}

# Funder-only org (no recipient data)
_ORG_SUMMARY_FUNDER_ONLY = {
    "self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1098765/",
    "grants_made": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1098765/grants_made/",
    "grants_received": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1098765/grants_received/",
    "funder": {
        "aggregate": {
            "grants": 500,
            "earliest_grant_date": "2020-01-01",
            "latest_grant_date": "2025-01-01",
            "currencies": {
                "GBP": {
                    "avg": 50000.0,
                    "max": 500000.0,
                    "min": 500.0,
                    "total": 25000000.0,
                    "grants": 500,
                }
            },
        }
    },
    "recipient": None,
    "publisher": None,
    "org_id": "GB-CHC-1098765",
    "name": "National Lottery Community Fund",
    "linked_orgs": [],
}

# 404 response — truly unknown org_id
_ORG_SUMMARY_NOT_FOUND = {
    "detail": "Not found.",
}

# Org with no grants — funder and recipient both null
_ORG_SUMMARY_NO_GRANTS = {
    "self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-5555555/",
    "grants_made": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-5555555/grants_made/",
    "grants_received": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-5555555/grants_received/",
    "funder": None,
    "recipient": None,
    "publisher": None,
    "org_id": "GB-CHC-5555555",
    "name": "Some Org With No Grants",
    "linked_orgs": [],
}

_GRANTS_RECEIVED_RESPONSE = {
    "count": 79,
    "next": None,
    "previous": None,
    "results": [
        {
            "grant_id": "360G-LondonCatalyst-1230062400000DxiudAAB",
            "data": {
                "id": "360G-LondonCatalyst-1230062400000DxiudAAB",
                "title": "The Trussell Trust - 1",
                "currency": "GBP",
                "awardDate": "2014-08-20T00:00:00+00:00",
                "description": "London Development Worker - to grow/support at least one foodbank in each London borough",
                "amountAwarded": 15000,
                "grantProgramme": [{"title": "Special Interest"}],
                "fundingOrganization": [
                    {"id": "GB-CHC-1066739", "name": "London Catalyst"}
                ],
                "recipientOrganization": [
                    {"id": "GB-CHC-1110522", "name": "The Trussell Trust", "charityNumber": "1110522"}
                ],
            },
            "data_license": {
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
            },
            "publisher": {"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1066739/", "org_id": "GB-CHC-1066739"},
            "recipients": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/", "org_id": "GB-CHC-1110522"}],
            "funders": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1066739/", "org_id": "GB-CHC-1066739"}],
        },
        {
            "grant_id": "360G-YBSCF-508",
            "data": {
                "id": "360G-YBSCF-508",
                "title": "Grant to BEXHILL FOODBANK",
                "currency": "GBP",
                "awardDate": "2023-05-02T00:00:00+00:00",
                "description": "Funding for food",
                "amountAwarded": 500,
                "grantProgramme": [
                    {"title": "Yorkshire Building Society Charitable Foundation Small Change Big Difference Fund"}
                ],
                "fundingOrganization": [
                    {"id": "GB-CHC-227905", "name": "Yorkshire Building Society Charitable Foundation"}
                ],
                "recipientOrganization": [
                    {"id": "GB-CHC-1110522", "name": "The Trussell Trust"}
                ],
            },
            "data_license": {
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
            },
            "publisher": {"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-227905/", "org_id": "GB-CHC-227905"},
            "recipients": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/", "org_id": "GB-CHC-1110522"}],
            "funders": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-227905/", "org_id": "GB-CHC-227905"}],
        },
    ],
}

_GRANTS_MADE_RESPONSE = {
    "count": 2326,
    "next": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/grants_made/?limit=100&offset=100&page_size=2",
    "previous": None,
    "results": [
        {
            "grant_id": "360G-TrussellTrust-L1EustS",
            "data": {
                "id": "360G-TrussellTrust-L1EustS",
                "title": "Grant to Euston Foodbank",
                "currency": "GBP",
                "awardDate": "2018-12-12T00:00:00+00:00",
                "description": "New foodbank manager",
                "amountAwarded": 51750,
                "grantProgramme": [{"title": "Fight Hunger, Create Change"}],
                "fundingOrganization": [
                    {"id": "GB-CHC-1110522", "name": "Trussell"}
                ],
                "recipientOrganization": [
                    {"id": "GB-CHC-1172880", "name": "Euston Foodbank", "charityNumber": "1172880"}
                ],
            },
            "data_license": {
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
            },
            "publisher": {"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/", "org_id": "GB-CHC-1110522"},
            "recipients": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1172880/", "org_id": "GB-CHC-1172880"}],
            "funders": [{"self": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/", "org_id": "GB-CHC-1110522"}],
        },
    ],
}

_GRANTS_EMPTY_RESPONSE = {
    "count": 0,
    "next": None,
    "previous": None,
    "results": [],
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
        summary = await fetch_grant_summary("GB-CHC-1110522")

    assert summary is not None
    assert summary.org_id == "GB-CHC-1110522"
    assert summary.is_funder is True
    assert summary.is_recipient is True
    assert summary.grants_received_count == 79
    assert summary.grants_received_total == 24381537.93
    assert summary.grants_made_count == 2326
    assert summary.grants_made_total == 89360877.93


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
    resp = _mock_response(404, _ORG_SUMMARY_NOT_FOUND)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-XXNONEXIST")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_no_grants_returns_none():
    """An org that exists but has no grants (funder and recipient both null) returns None."""
    resp = _mock_response(200, _ORG_SUMMARY_NO_GRANTS)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-5555555")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_handles_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-1110522")

    assert summary is None


@pytest.mark.asyncio
async def test_fetch_grant_summary_hits_correct_endpoint():
    resp = _mock_response(200, _ORG_SUMMARY_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        await fetch_grant_summary("GB-CHC-1110522")

    url = mock_client.get.call_args.args[0]
    assert "api.threesixtygiving.org" in url
    assert "/org/GB-CHC-1110522" in url


@pytest.mark.asyncio
async def test_fetch_grant_summary_extracts_avg_min_max():
    """Verify avg, min, max are parsed from the currencies sub-object."""
    resp = _mock_response(200, _ORG_SUMMARY_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        summary = await fetch_grant_summary("GB-CHC-1110522")

    assert summary is not None
    assert summary.grants_received_avg == 308627.06
    assert summary.grants_received_min == 160.0
    assert summary.grants_received_max == 3500000.0
    assert summary.grants_made_avg == 38418.26
    assert summary.grants_made_min == 25.0
    assert summary.grants_made_max == 659184.62


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
        grants = await fetch_grants_received("GB-CHC-1110522")

    assert len(grants) == 2
    assert grants[0].grant_id == "360G-LondonCatalyst-1230062400000DxiudAAB"
    assert grants[0].title == "The Trussell Trust - 1"
    assert grants[0].amount == 15000
    assert grants[0].funder_name == "London Catalyst"
    assert grants[0].funder_org_id == "GB-CHC-1066739"
    assert grants[0].recipient_org_id == "GB-CHC-1110522"
    assert grants[0].recipient_name == "The Trussell Trust"


@pytest.mark.asyncio
async def test_fetch_grants_made_returns_grant_records():
    # _GRANTS_MADE_RESPONSE has next != None, so mock a second page with no results
    page2 = {"count": 2326, "next": None, "previous": "...", "results": []}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        _mock_response(200, _GRANTS_MADE_RESPONSE),
        _mock_response(200, page2),
    ])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_made("GB-CHC-1110522")

    assert len(grants) == 1
    assert grants[0].grant_id == "360G-TrussellTrust-L1EustS"
    assert grants[0].amount == 51750
    assert grants[0].recipient_name == "Euston Foodbank"
    assert grants[0].funder_name == "Trussell"


@pytest.mark.asyncio
async def test_fetch_grants_received_empty_results():
    resp = _mock_response(200, _GRANTS_EMPTY_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1110522")

    assert grants == []


@pytest.mark.asyncio
async def test_fetch_grants_received_handles_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1110522")

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
        grants = await fetch_grants_received("GB-CHC-1110522")

    assert grants[0].award_date == "2014-08-20"


@pytest.mark.asyncio
async def test_fetch_grants_received_strips_timezone_from_award_date():
    """Award dates include timezone offset (+00:00); date part only is kept."""
    resp = _mock_response(200, _GRANTS_RECEIVED_RESPONSE)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1110522")

    assert grants[0].award_date == "2014-08-20"
    assert "T" not in grants[0].award_date
    assert "+" not in grants[0].award_date


@pytest.mark.asyncio
async def test_fetch_grants_received_handles_missing_data_field():
    """If a result is missing the 'data' key, it's skipped gracefully."""
    response_with_missing_data = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {"grant_id": "360G-broken", "data": None},
        ],
    }
    resp = _mock_response(200, response_with_missing_data)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_received("GB-CHC-1110522")

    assert grants == []


@pytest.mark.asyncio
async def test_fetch_grants_made_follows_pagination():
    """When 'next' is set, the client fetches the next page too."""
    page1 = {
        "count": 3,
        "next": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/grants_made/?page=2",
        "previous": None,
        "results": [
            {
                "grant_id": "360G-page1-1",
                "data": {
                    "id": "360G-page1-1",
                    "title": "Grant page1-1",
                    "currency": "GBP",
                    "awardDate": "2024-01-01T00:00:00+00:00",
                    "amountAwarded": 1000,
                    "fundingOrganization": [{"id": "GB-CHC-1110522", "name": "Trussell"}],
                    "recipientOrganization": [{"id": "GB-CHC-2222222", "name": "Org A"}],
                },
            },
        ],
    }
    page2 = {
        "count": 3,
        "next": None,
        "previous": "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1110522/grants_made/?page=1",
        "results": [
            {
                "grant_id": "360G-page2-1",
                "data": {
                    "id": "360G-page2-1",
                    "title": "Grant page2-1",
                    "currency": "GBP",
                    "awardDate": "2024-06-01T00:00:00+00:00",
                    "amountAwarded": 2000,
                    "fundingOrganization": [{"id": "GB-CHC-1110522", "name": "Trussell"}],
                    "recipientOrganization": [{"id": "GB-CHC-3333333", "name": "Org B"}],
                },
            },
        ],
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        _mock_response(200, page1),
        _mock_response(200, page2),
    ])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.threesixty_giving_api.httpx.AsyncClient", return_value=mock_client):
        grants = await fetch_grants_made("GB-CHC-1110522", limit=50)

    assert len(grants) == 2
    assert grants[0].grant_id == "360G-page1-1"
    assert grants[1].grant_id == "360G-page2-1"


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