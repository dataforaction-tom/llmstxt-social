"""Tests for the Beacon CRM enricher (Pattern A — read-only).

Beacon CRM is a constituent/donor management system. This enricher reads
constituents, donations, and case-management records from Beacon's REST API
and maps donations + cases to Open Org evidence[] items.

Tests mock all HTTP — no network access.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmstxt_core.enrichers.beacon_crm import (
    BeaconCase,
    BeaconClient,
    BeaconConstituent,
    BeaconDonation,
    cases_to_evidence,
    donations_to_evidence,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_beacon_constituent_accepts_all_fields():
    c = BeaconConstituent(
        id="c-001",
        name="Jane Doe",
        email="jane@example.org",
        type="individual",
        tags=["major-donor", "newsletter"],
        custom_fields={"region": "South"},
    )
    assert c.id == "c-001"
    assert c.name == "Jane Doe"
    assert c.email == "jane@example.org"
    assert c.type == "individual"
    assert c.tags == ["major-donor", "newsletter"]
    assert c.custom_fields == {"region": "South"}


def test_beacon_donation_accepts_all_fields():
    d = BeaconDonation(
        id="d-100",
        amount=50000,
        currency="GBP",
        date="2024-03-15",
        fund="General Fund",
        campaign="Spring Appeal 2024",
    )
    assert d.id == "d-100"
    assert d.amount == 50000
    assert d.currency == "GBP"
    assert d.date == "2024-03-15"
    assert d.fund == "General Fund"
    assert d.campaign == "Spring Appeal 2024"


def test_beacon_case_accepts_all_fields():
    case = BeaconCase(
        id="case-9",
        title="Housing support referral",
        status="open",
        opened_date="2024-01-10",
        closed_date=None,
        description="Client needed emergency housing advice.",
    )
    assert case.id == "case-9"
    assert case.title == "Housing support referral"
    assert case.status == "open"
    assert case.opened_date == "2024-01-10"
    assert case.closed_date is None
    assert case.description == "Client needed emergency housing advice."


# ---------------------------------------------------------------------------
# API response fixtures
# ---------------------------------------------------------------------------

_CONSTITUENT_RESPONSE = {
    "id": "c-001",
    "name": "Jane Doe",
    "email": "jane@example.org",
    "type": "individual",
    "tags": ["major-donor", "newsletter"],
    "custom_fields": {"region": "South"},
}

_SEARCH_RESPONSE = {
    "data": [
        _CONSTITUENT_RESPONSE,
        {
            "id": "c-002",
            "name": "Acme Corp",
            "email": "giving@acme.com",
            "type": "organisation",
            "tags": ["corporate"],
            "custom_fields": {},
        },
    ],
    "meta": {"page": 1, "per_page": 20, "total": 2},
}

_DONATIONS_RESPONSE = {
    "data": [
        {
            "id": "d-100",
            "amount": 50000,
            "currency": "GBP",
            "date": "2024-03-15",
            "fund": "General Fund",
            "campaign": "Spring Appeal 2024",
        },
        {
            "id": "d-101",
            "amount": 25000,
            "currency": "GBP",
            "date": "2023-11-01",
            "fund": "Hardship Fund",
            "campaign": "Winter Appeal 2023",
        },
    ],
    "meta": {"page": 1, "per_page": 50, "total": 2},
}

_CASES_RESPONSE = {
    "data": [
        {
            "id": "case-9",
            "title": "Housing support referral",
            "status": "open",
            "opened_date": "2024-01-10",
            "closed_date": None,
            "description": "Client needed emergency housing advice.",
        },
    ],
    "meta": {"page": 1, "per_page": 50, "total": 1},
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


def _build_mock_client() -> AsyncMock:
    """Return an AsyncMock configured as an httpx.AsyncClient."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


# ---------------------------------------------------------------------------
# BeaconClient.get_constituent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_constituent_returns_constituent_on_200():
    resp = _mock_response(200, _CONSTITUENT_RESPONSE)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    constituent = await client.get_constituent("c-001")

    assert constituent is not None
    assert constituent.id == "c-001"
    assert constituent.name == "Jane Doe"
    assert constituent.email == "jane@example.org"
    assert constituent.type == "individual"
    assert constituent.tags == ["major-donor", "newsletter"]


@pytest.mark.asyncio
async def test_get_constituent_returns_none_on_404():
    resp = _mock_response(404)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    constituent = await client.get_constituent("nope")

    assert constituent is None


# ---------------------------------------------------------------------------
# BeaconClient.search_constituents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_constituents_returns_list():
    resp = _mock_response(200, _SEARCH_RESPONSE)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    results = await client.search_constituents("Jane")

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0].id == "c-001"
    assert results[1].id == "c-002"
    assert results[1].type == "organisation"


# ---------------------------------------------------------------------------
# BeaconClient.get_donations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_donations_returns_donations():
    resp = _mock_response(200, _DONATIONS_RESPONSE)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    donations = await client.get_donations("c-001")

    assert len(donations) == 2
    assert donations[0].id == "d-100"
    assert donations[0].amount == 50000
    assert donations[0].currency == "GBP"
    assert donations[0].fund == "General Fund"
    assert donations[1].campaign == "Winter Appeal 2023"


# ---------------------------------------------------------------------------
# BeaconClient.get_cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cases_returns_cases():
    resp = _mock_response(200, _CASES_RESPONSE)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    cases = await client.get_cases("c-001")

    assert len(cases) == 1
    assert cases[0].id == "case-9"
    assert cases[0].title == "Housing support referral"
    assert cases[0].status == "open"
    assert cases[0].closed_date is None


# ---------------------------------------------------------------------------
# Network-error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_constituent_handles_network_error():
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    constituent = await client.get_constituent("c-001")

    assert constituent is None


@pytest.mark.asyncio
async def test_get_donations_handles_network_error():
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    donations = await client.get_donations("c-001")

    assert donations == []


@pytest.mark.asyncio
async def test_get_cases_handles_network_error():
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    cases = await client.get_cases("c-001")

    assert cases == []


@pytest.mark.asyncio
async def test_search_constituents_handles_network_error():
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

    client = BeaconClient(api_key="test-key", http_client_factory=lambda: mock_client)
    results = await client.search_constituents("Jane")

    assert results == []


# ---------------------------------------------------------------------------
# Bearer auth header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_uses_bearer_auth_header():
    resp = _mock_response(200, _CONSTITUENT_RESPONSE)
    mock_client = _build_mock_client()
    mock_client.get = AsyncMock(return_value=resp)

    client = BeaconClient(api_key="secret-key-123", http_client_factory=lambda: mock_client)
    await client.get_constituent("c-001")

    call_kwargs = mock_client.get.call_args.kwargs
    headers = call_kwargs.get("headers", {})
    assert headers.get("Authorization") == "Bearer secret-key-123"


# ---------------------------------------------------------------------------
# donations_to_evidence
# ---------------------------------------------------------------------------


def test_donations_to_evidence_maps_donations_to_outcome_data():
    donations = [
        BeaconDonation(
            id="d-100",
            amount=50000,
            currency="GBP",
            date="2024-03-15",
            fund="General Fund",
            campaign="Spring Appeal 2024",
        ),
    ]
    items = donations_to_evidence(donations)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "outcome_data"
    assert item["date"] == "2024-03-15"
    assert "evidence_id" in item
    assert len(item["outcomes"]) > 0
    outcome = item["outcomes"][0]
    assert outcome["metric"] == "donation_amount"
    assert outcome["value"] == 50000
    assert outcome["currency"] == "GBP"


def test_donations_to_evidence_empty_list():
    assert donations_to_evidence([]) == []


def test_donations_to_evidence_generates_unique_ids():
    donations = [
        BeaconDonation(
            id="d-a",
            amount=10000,
            currency="GBP",
            date="2024-01-01",
            fund="Fund A",
            campaign="C1",
        ),
        BeaconDonation(
            id="d-b",
            amount=20000,
            currency="GBP",
            date="2024-02-01",
            fund="Fund B",
            campaign="C2",
        ),
    ]
    items = donations_to_evidence(donations)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# cases_to_evidence
# ---------------------------------------------------------------------------


def test_cases_to_evidence_maps_cases_to_case_study():
    cases = [
        BeaconCase(
            id="case-9",
            title="Housing support referral",
            status="open",
            opened_date="2024-01-10",
            closed_date=None,
            description="Client needed emergency housing advice.",
        ),
    ]
    items = cases_to_evidence(cases)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "case_study"
    assert item["title"] == "Housing support referral"
    assert item["date"] == "2024-01-10"
    assert "evidence_id" in item
    assert item["description"] == "Client needed emergency housing advice."


def test_cases_to_evidence_empty_list():
    assert cases_to_evidence([]) == []


def test_cases_to_evidence_generates_unique_ids():
    cases = [
        BeaconCase(
            id="case-a",
            title="Case A",
            status="closed",
            opened_date="2024-01-01",
            closed_date="2024-02-01",
            description="desc A",
        ),
        BeaconCase(
            id="case-b",
            title="Case B",
            status="open",
            opened_date="2024-03-01",
            closed_date=None,
            description="desc B",
        ),
    ]
    items = cases_to_evidence(cases)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)