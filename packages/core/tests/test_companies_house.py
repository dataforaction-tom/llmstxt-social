"""Tests for the Companies House enricher.

Companies House provides governance data (registered office, officers/directors,
PSC/beneficial ownership, filing history, accounts) for UK companies. Most
medium+ UK charities are companies limited by guarantee, so the Charity
Commission enricher's ``company_number`` field is the bridge.

API: https://api.company-information.service.gov.uk
Auth: HTTP Basic with API key as username, empty password.
Rate limit: 600 requests per 5 minutes.

Tests mock all HTTP — no network access.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmstxt_core.enrichers.companies_house import (
    CompanyData,
    FilingRecord,
    OfficerRecord,
    PSCRecord,
    fetch_company_data,
    filing_history_to_evidence,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_company_data_accepts_all_fields():
    officer = OfficerRecord(
        name="Jane Doe",
        officer_role="director",
        appointed_on="2020-01-01",
        resigned_on=None,
    )
    filing = FilingRecord(
        date="2024-03-31",
        type="AA",
        description="Full accounts made up to 31 March 2024",
        transaction_id="MzAwMjA3NjUzMWFfZGlxMmVucXJfMQ",
    )
    psc = PSCRecord(
        name="Jane Doe",
        natures_of_control=["ownership-of-shares-75-to-100-percent"],
        notified_on="2020-01-01",
        ceased_on=None,
    )
    data = CompanyData(
        name="Riverside Trust",
        company_number="01234567",
        status="active",
        type="ltd",
        date_of_creation="2000-01-01",
        date_of_cessation=None,
        jurisdiction="england-wales",
        sic_codes=["82990"],
        registered_office={"locality": "London", "postal_code": "SW1A 1AA"},
        accounts_next_due="2025-03-31",
        accounts_overdue=False,
        last_accounts_made_up_to="2024-03-31",
        officers=[officer],
        filing_history=[filing],
        psc=[psc],
    )
    assert data.name == "Riverside Trust"
    assert data.company_number == "01234567"
    assert data.status == "active"
    assert data.officers[0].name == "Jane Doe"
    assert data.filing_history[0].type == "AA"
    assert data.psc[0].natures_of_control == ["ownership-of-shares-75-to-100-percent"]


def test_company_data_optional_fields_default():
    data = CompanyData(
        name="Test",
        company_number="01234567",
        status="active",
    )
    assert data.type is None
    assert data.date_of_creation is None
    assert data.date_of_cessation is None
    assert data.jurisdiction is None
    assert data.sic_codes == []
    assert data.registered_office is None
    assert data.accounts_next_due is None
    assert data.accounts_overdue is None
    assert data.last_accounts_made_up_to is None
    assert data.officers == []
    assert data.filing_history == []
    assert data.psc == []


def test_officer_record_resigned_on_defaults_none():
    off = OfficerRecord(name="Bob", officer_role="secretary", appointed_on="2019-06-15")
    assert off.resigned_on is None


def test_filing_record_has_required_fields():
    f = FilingRecord(
        date="2024-01-01",
        type="CS01",
        description="Confirmation statement",
        transaction_id="abc123",
    )
    assert f.date == "2024-01-01"
    assert f.type == "CS01"


def test_psc_record_ceased_on_defaults_none():
    p = PSCRecord(
        name="Alice",
        natures_of_control=["ownership-of-shares-50-to-75-percent"],
        notified_on="2020-03-01",
    )
    assert p.ceased_on is None


# ---------------------------------------------------------------------------
# fetch_company_data — HTTP mocking
# ---------------------------------------------------------------------------

# A realistic company-profile response from Companies House
_PROFILE_RESPONSE = {
    "company_name": "RIVERSIDE COMMUNITY TRUST LIMITED",
    "company_number": "01234567",
    "company_status": "active",
    "type": "ltd",
    "date_of_creation": "2001-03-15",
    "jurisdiction": "england-wales",
    "sic_codes": ["94990", "82990"],
    "registered_office_address": {
        "address_line_1": "10 High Street",
        "locality": "Great Yarmouth",
        "postal_code": "NR30 1AB",
        "country": "England",
    },
    "accounts": {
        "next_due": "2025-03-31",
        "overdue": False,
        "last_accounts": {
            "made_up_to": "2024-03-31",
            "period_end_on": "2024-03-31",
            "period_start_on": "2023-04-01",
        },
    },
}

_OFFICERS_RESPONSE = {
    "active_count": 3,
    "items": [
        {
            "name": "Doe, Jane",
            "officer_role": "director",
            "appointed_on": "2020-01-01",
        },
        {
            "name": "Smith, John",
            "officer_role": "director",
            "appointed_on": "2018-06-15",
            "resigned_on": "2023-12-31",
        },
        {
            "name": "Brown, Bob",
            "officer_role": "secretary",
            "appointed_on": "2019-03-01",
        },
    ],
}

_FILINGS_RESPONSE = {
    "items": [
        {
            "category": "accounts",
            "date": "2024-04-15",
            "description": "Full accounts made up to 31 March 2024",
            "transaction_id": "MzAwMjA3NjUzMWFfZGlxMmVucXJfMQ",
            "type": "AA",
        },
        {
            "category": "confirmation-statement",
            "date": "2024-01-10",
            "description": "Confirmation statement made on 10 January 2024",
            "transaction_id": "abc456",
            "type": "CS01",
        },
    ],
}

_PSC_RESPONSE = {
    "items": [
        {
            "name": "Doe, Jane",
            "kind": "individual-person-with-significant-control",
            "natures_of_control": [
                "ownership-of-shares-75-to-100-percent",
                "right-to-appoint-and-remove-directors",
            ],
            "notified_on": "2020-01-01",
        },
    ],
}


def _mock_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_fetch_company_data_returns_company_data_on_200():
    """A successful fetch returns a populated CompanyData."""
    responses = [
        _mock_response(200, _PROFILE_RESPONSE),
        _mock_response(200, _OFFICERS_RESPONSE),
        _mock_response(200, _FILINGS_RESPONSE),
        _mock_response(200, _PSC_RESPONSE),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        data = await fetch_company_data("01234567", api_key="test-key")

    assert data is not None
    assert data.name == "RIVERSIDE COMMUNITY TRUST LIMITED"
    assert data.company_number == "01234567"
    assert data.status == "active"
    assert data.type == "ltd"
    assert data.date_of_creation == "2001-03-15"
    assert data.jurisdiction == "england-wales"
    assert data.sic_codes == ["94990", "82990"]
    assert data.registered_office["postal_code"] == "NR30 1AB"
    assert data.accounts_next_due == "2025-03-31"
    assert data.accounts_overdue is False
    assert data.last_accounts_made_up_to == "2024-03-31"
    # officers
    assert len(data.officers) == 3
    assert data.officers[0].name == "Doe, Jane"
    assert data.officers[0].officer_role == "director"
    assert data.officers[1].resigned_on == "2023-12-31"
    # filing history
    assert len(data.filing_history) == 2
    assert data.filing_history[0].type == "AA"
    assert data.filing_history[0].date == "2024-04-15"
    # psc
    assert len(data.psc) == 1
    assert data.psc[0].name == "Doe, Jane"
    assert "ownership-of-shares-75-to-100-percent" in data.psc[0].natures_of_control


@pytest.mark.asyncio
async def test_fetch_company_data_returns_none_on_404():
    """Company not found returns None, not an exception."""
    responses = [_mock_response(404)]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        data = await fetch_company_data("99999999", api_key="test-key")

    assert data is None


@pytest.mark.asyncio
async def test_fetch_company_data_handles_missing_optional_fields():
    """A sparse profile (no accounts, no sic_codes, no officers) still works."""
    sparse_profile = {
        "company_name": "MINIMAL LTD",
        "company_number": "00000001",
        "company_status": "active",
    }
    responses = [
        _mock_response(200, sparse_profile),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        data = await fetch_company_data("00000001", api_key="test-key")

    assert data is not None
    assert data.name == "MINIMAL LTD"
    assert data.sic_codes == []
    assert data.officers == []
    assert data.filing_history == []
    assert data.psc == []
    assert data.accounts_next_due is None
    assert data.last_accounts_made_up_to is None


@pytest.mark.asyncio
async def test_fetch_company_data_loads_api_key_from_env():
    """When api_key is not passed, it's loaded from COMPANIES_HOUSE_API_KEY env var."""
    responses = [
        _mock_response(200, _PROFILE_RESPONSE),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        with patch.dict("os.environ", {"COMPANIES_HOUSE_API_KEY": "env-key"}):
            data = await fetch_company_data("01234567")

    assert data is not None
    # Verify the auth header used HTTP Basic with the env key (base64-encoded)
    call_kwargs = mock_client.get.call_args_list[0].kwargs
    headers = call_kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")
    decoded = base64.b64decode(headers["Authorization"].removeprefix("Basic ")).decode()
    assert "env-key" in decoded


@pytest.mark.asyncio
async def test_fetch_company_data_returns_none_without_api_key():
    """No API key available (None arg + no env var) returns None."""
    with patch.dict("os.environ", {}, clear=True):
        data = await fetch_company_data("01234567")
    assert data is None


@pytest.mark.asyncio
async def test_fetch_company_data_uses_basic_auth():
    """Companies House uses HTTP Basic auth with API key as username, empty password."""
    responses = [
        _mock_response(200, _PROFILE_RESPONSE),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
        _mock_response(200, {"items": []}),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        await fetch_company_data("01234567", api_key="my-key")

    first_call = mock_client.get.call_args_list[0]
    headers = first_call.kwargs.get("headers", {})
    # HTTP Basic: base64("my-key:")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_fetch_company_data_hits_correct_endpoints():
    """Verify the four API endpoints are called with the right paths."""
    responses = [
        _mock_response(200, _PROFILE_RESPONSE),
        _mock_response(200, _OFFICERS_RESPONSE),
        _mock_response(200, _FILINGS_RESPONSE),
        _mock_response(200, _PSC_RESPONSE),
    ]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        await fetch_company_data("01234567", api_key="test-key")

    urls = [c.args[0] for c in mock_client.get.call_args_list]
    assert "/company/01234567" in urls[0]
    assert "/company/01234567/officers" in urls[1]
    assert "/company/01234567/filing-history" in urls[2]
    assert "/company/01234567/persons-with-significant-control" in urls[3]


@pytest.mark.asyncio
async def test_fetch_company_data_handles_network_error():
    """A network error returns None, not an exception."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("llmstxt_core.enrichers.companies_house.httpx.AsyncClient", return_value=mock_client):
        data = await fetch_company_data("01234567", api_key="test-key")

    assert data is None


# ---------------------------------------------------------------------------
# filing_history_to_evidence — maps filings to evidence[] items
# ---------------------------------------------------------------------------


def test_filing_history_to_evidence_maps_accounts_filing():
    """An accounts filing becomes an evidence item with type 'annual_report'."""
    filing = FilingRecord(
        date="2024-04-15",
        type="AA",
        description="Full accounts made up to 31 March 2024",
        transaction_id="tx001",
    )
    items = filing_history_to_evidence([filing], base_url="https://find-and-update.company-information.service.gov.uk")
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "annual_report"
    assert "accounts" in item["title"].lower()
    assert item["date"] == "2024-04-15"
    assert item["url"] is not None
    assert "tx001" in item["url"]


def test_filing_history_to_evidence_maps_confirmation_statement():
    """A confirmation statement becomes an evidence item with type 'annual_report'."""
    filing = FilingRecord(
        date="2024-01-10",
        type="CS01",
        description="Confirmation statement made on 10 January 2024",
        transaction_id="tx002",
    )
    items = filing_history_to_evidence([filing])
    assert len(items) == 1
    assert items[0]["evidence_type"] == "annual_report"


def test_filing_history_to_evidence_skips_non_report_filings():
    """Non-report filings (e.g. incorporation) are skipped."""
    filings = [
        FilingRecord(date="2001-03-15", type="INC", description="Incorporation", transaction_id="t1"),
        FilingRecord(date="2024-04-15", type="AA", description="Full accounts", transaction_id="t2"),
    ]
    items = filing_history_to_evidence(filings)
    assert len(items) == 1
    assert items[0]["evidence_type"] == "annual_report"


def test_filing_history_to_evidence_empty_list():
    """Empty filing history produces empty evidence list."""
    assert filing_history_to_evidence([]) == []


def test_filing_history_to_evidence_generates_unique_ids():
    """Each evidence item gets a unique evidence_id."""
    filings = [
        FilingRecord(date="2024-04-15", type="AA", description="Full accounts 2024", transaction_id="t1"),
        FilingRecord(date="2023-04-15", type="AA", description="Full accounts 2023", transaction_id="t2"),
    ]
    items = filing_history_to_evidence(filings)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)  # all unique