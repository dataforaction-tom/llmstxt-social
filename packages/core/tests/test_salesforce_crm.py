"""Tests for the Salesforce CRM enricher (Pattern A read-only).

Salesforce Nonprofit Cloud stores org accounts, grants/opportunities, and
contacts. This enricher reads via the Salesforce REST API (v60.0) with
OAuth2 bearer-token auth and maps grants/contacts to Open Org evidence[] items.

Endpoints:
    GET /sobjects/Account/{id}             — org account detail
    GET /query/?q={soql}                    — SOQL query (opportunities, contacts)
    GET /sobjects/{type}/{id}              — sobject detail

Auth: ``Authorization: Bearer {access_token}`` header.

Tests mock all HTTP — no network access.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmstxt_core.enrichers.salesforce_crm import (
    SalesforceAccount,
    SalesforceClient,
    SalesforceContact,
    SalesforceOpportunity,
    contacts_to_evidence,
    opportunities_to_evidence,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_salesforce_account_accepts_all_fields():
    acct = SalesforceAccount(
        id="0018V00000ABCd123",
        name="Riverside Community Trust",
        type="Nonprofit",
        billing_address={"city": "London", "country": "UK"},
        website="https://riverside.org",
        description="Community support charity",
        industry="Nonprofit",
    )
    assert acct.id == "0018V00000ABCd123"
    assert acct.name == "Riverside Community Trust"
    assert acct.type == "Nonprofit"
    assert acct.billing_address["city"] == "London"
    assert acct.website == "https://riverside.org"
    assert acct.description == "Community support charity"
    assert acct.industry == "Nonprofit"


def test_salesforce_opportunity_accepts_all_fields():
    opp = SalesforceOpportunity(
        id="0068V00000XYZd456",
        name="Community Food Programme Grant",
        amount=50000.0,
        stage="Closed Won",
        close_date="2024-03-15",
        type="Grant",
        account_id="0018V00000ABCd123",
    )
    assert opp.id == "0068V00000XYZd456"
    assert opp.name == "Community Food Programme Grant"
    assert opp.amount == 50000.0
    assert opp.stage == "Closed Won"
    assert opp.close_date == "2024-03-15"
    assert opp.type == "Grant"
    assert opp.account_id == "0018V00000ABCd123"


def test_salesforce_contact_accepts_all_fields():
    contact = SalesforceContact(
        id="0038V00000DEFd789",
        name="Jane Doe",
        email="jane.doe@riverside.org",
        role="Programme Director",
        account_id="0018V00000ABCd123",
    )
    assert contact.id == "0038V00000DEFd789"
    assert contact.name == "Jane Doe"
    assert contact.email == "jane.doe@riverside.org"
    assert contact.role == "Programme Director"
    assert contact.account_id == "0018V00000ABCd123"


# ---------------------------------------------------------------------------
# API response fixtures
# ---------------------------------------------------------------------------

_ACCOUNT_RESPONSE = {
    "Id": "0018V00000ABCd123",
    "Name": "Riverside Community Trust",
    "Type": "Nonprofit",
    "BillingAddress": {"city": "London", "country": "UK"},
    "Website": "https://riverside.org",
    "Description": "Community support charity",
    "Industry": "Nonprofit",
}

_QUERY_OPPORTUNITIES_RESPONSE = {
    "totalSize": 2,
    "records": [
        {
            "Id": "0068V00000XYZd456",
            "Name": "Community Food Programme Grant",
            "Amount": 50000.0,
            "StageName": "Closed Won",
            "CloseDate": "2024-03-15",
            "Type": "Grant",
            "AccountId": "0018V00000ABCd123",
        },
        {
            "Id": "0068V00000XYZd789",
            "Name": "Individual Donation",
            "Amount": 500.0,
            "StageName": "Closed Won",
            "CloseDate": "2024-01-10",
            "Type": "Donation",
            "AccountId": "0018V00000ABCd123",
        },
    ],
    "nextRecordsUrl": None,
}

_QUERY_CONTACTS_RESPONSE = {
    "totalSize": 1,
    "records": [
        {
            "Id": "0038V00000DEFd789",
            "Name": "Jane Doe",
            "Email": "jane.doe@riverside.org",
            "Role__c": "Programme Director",
            "AccountId": "0018V00000ABCd123",
        },
    ],
    "nextRecordsUrl": None,
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


def _mock_http_client(get_responses=None, get_side_effect=None):
    """Build a mock httpx.AsyncClient suitable for SalesforceClient.

    The client is returned by ``http_client_factory`` (or the default
    httpx.AsyncClient). We mock the factory so we never touch the network.
    """
    mock_client = AsyncMock()
    if get_side_effect is not None:
        mock_client.get = AsyncMock(side_effect=get_side_effect)
    elif get_responses is not None:
        mock_client.get = AsyncMock(side_effect=list(get_responses))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ---------------------------------------------------------------------------
# SalesforceClient.get_account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_account_returns_account_on_200():
    resp = _mock_response(200, _ACCOUNT_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    account = await client.get_account("0018V00000ABCd123")

    assert account is not None
    assert account.id == "0018V00000ABCd123"
    assert account.name == "Riverside Community Trust"
    assert account.type == "Nonprofit"
    assert account.billing_address["city"] == "London"
    assert account.website == "https://riverside.org"
    assert account.description == "Community support charity"
    assert account.industry == "Nonprofit"


@pytest.mark.asyncio
async def test_get_account_returns_none_on_404():
    resp = _mock_response(404)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    account = await client.get_account("001nonexistent")

    assert account is None


# ---------------------------------------------------------------------------
# SalesforceClient.get_opportunities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_opportunities_returns_list():
    resp = _mock_response(200, _QUERY_OPPORTUNITIES_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    opps = await client.get_opportunities("0018V00000ABCd123")

    assert len(opps) == 2
    assert isinstance(opps[0], SalesforceOpportunity)
    assert opps[0].id == "0068V00000XYZd456"
    assert opps[0].name == "Community Food Programme Grant"
    assert opps[0].amount == 50000.0
    assert opps[0].stage == "Closed Won"
    assert opps[0].close_date == "2024-03-15"
    assert opps[0].type == "Grant"
    assert opps[0].account_id == "0018V00000ABCd123"


@pytest.mark.asyncio
async def test_get_opportunities_uses_soql_query():
    """get_opportunities should issue a SOQL query via the /query/ endpoint."""
    resp = _mock_response(200, _QUERY_OPPORTUNITIES_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    await client.get_opportunities("0018V00000ABCd123")

    # Verify the request hit the /query/ endpoint
    url = mock_client.get.call_args.args[0]
    assert "/query/" in url
    # Verify the SOQL query mentions Opportunity and the AccountId
    # The SOQL is passed as the `q` query param (in params kwarg or in URL)
    call_kwargs = mock_client.get.call_args.kwargs
    params = call_kwargs.get("params", {})
    soql = params.get("q", "")
    assert "Opportunity" in soql
    assert "0018V00000ABCd123" in soql


# ---------------------------------------------------------------------------
# SalesforceClient.get_contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_contacts_returns_list():
    resp = _mock_response(200, _QUERY_CONTACTS_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    contacts = await client.get_contacts("0018V00000ABCd123")

    assert len(contacts) == 1
    assert isinstance(contacts[0], SalesforceContact)
    assert contacts[0].id == "0038V00000DEFd789"
    assert contacts[0].name == "Jane Doe"
    assert contacts[0].email == "jane.doe@riverside.org"
    assert contacts[0].role == "Programme Director"
    assert contacts[0].account_id == "0018V00000ABCd123"


# ---------------------------------------------------------------------------
# SalesforceClient.query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_returns_records_list():
    resp = _mock_response(200, _QUERY_OPPORTUNITIES_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    records = await client.query("SELECT Id, Name FROM Opportunity")

    assert isinstance(records, list)
    assert len(records) == 2
    assert records[0]["Id"] == "0068V00000XYZd456"


# ---------------------------------------------------------------------------
# SalesforceClient error handling + auth header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_handles_network_error():
    mock_client = _mock_http_client(get_side_effect=httpx.ConnectError("refused"))

    client = SalesforceClient(
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    # get_account should return None on network error (not raise)
    account = await client.get_account("0018V00000ABCd123")
    assert account is None

    # query should return empty list on network error (not raise)
    records = await client.query("SELECT Id FROM Account")
    assert records == []


@pytest.mark.asyncio
async def test_client_uses_bearer_auth_header():
    """Every request must carry ``Authorization: Bearer {token}``."""
    resp = _mock_response(200, _ACCOUNT_RESPONSE)
    mock_client = _mock_http_client(get_responses=[resp])

    client = SalesforceClient(
        access_token="my-secret-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )
    await client.get_account("0018V00000ABCd123")

    headers = mock_client.get.call_args.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer my-secret-token"


# ---------------------------------------------------------------------------
# opportunities_to_evidence
# ---------------------------------------------------------------------------


def test_opportunities_to_evidence_maps_grants_to_outcome_data():
    opps = [
        SalesforceOpportunity(
            id="0068V00000XYZd456",
            name="Community Food Programme Grant",
            amount=50000.0,
            stage="Closed Won",
            close_date="2024-03-15",
            type="Grant",
            account_id="0018V00000ABCd123",
        ),
    ]
    items = opportunities_to_evidence(opps)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "outcome_data"
    assert "food" in item["title"].lower()
    assert item["date"] == "2024-03-15"
    # outcomes should include the amount
    assert len(item["outcomes"]) > 0
    outcome = item["outcomes"][0]
    assert outcome["value"] == 50000.0


def test_opportunities_to_evidence_skips_non_grant():
    opps = [
        SalesforceOpportunity(
            id="006-grant",
            name="Grant A",
            amount=10000.0,
            stage="Closed Won",
            close_date="2024-01-01",
            type="Grant",
            account_id="acct-1",
        ),
        SalesforceOpportunity(
            id="006-donation",
            name="Donation B",
            amount=500.0,
            stage="Closed Won",
            close_date="2024-02-01",
            type="Donation",
            account_id="acct-1",
        ),
        SalesforceOpportunity(
            id="006-program",
            name="Program C",
            amount=2000.0,
            stage="Closed Won",
            close_date="2024-03-01",
            type="Program",
            account_id="acct-1",
        ),
    ]
    items = opportunities_to_evidence(opps)
    assert len(items) == 1
    assert items[0]["evidence_type"] == "outcome_data"
    assert "Grant A" in items[0]["title"]


def test_opportunities_to_evidence_empty_list():
    assert opportunities_to_evidence([]) == []


def test_opportunities_to_evidence_generates_unique_ids():
    opps = [
        SalesforceOpportunity(
            id="006-a",
            name="Grant A",
            amount=10000.0,
            stage="Closed Won",
            close_date="2024-01-01",
            type="Grant",
            account_id="acct-1",
        ),
        SalesforceOpportunity(
            id="006-b",
            name="Grant B",
            amount=20000.0,
            stage="Closed Won",
            close_date="2024-02-01",
            type="Grant",
            account_id="acct-1",
        ),
    ]
    items = opportunities_to_evidence(opps)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# contacts_to_evidence
# ---------------------------------------------------------------------------


def test_contacts_to_evidence_maps_to_case_study():
    contacts = [
        SalesforceContact(
            id="0038V00000DEFd789",
            name="Jane Doe",
            email="jane.doe@riverside.org",
            role="Programme Director",
            account_id="0018V00000ABCd123",
        ),
    ]
    items = contacts_to_evidence(contacts)
    assert len(items) == 1
    item = items[0]
    assert item["evidence_type"] == "case_study"
    assert "Jane Doe" in item["title"]
    assert item["date"] is not None  # some date present


def test_contacts_to_evidence_empty_list():
    assert contacts_to_evidence([]) == []