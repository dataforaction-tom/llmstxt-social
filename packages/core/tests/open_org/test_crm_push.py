"""Tests for CRM Pattern B — one-way push from Open Org profile to CRM.

The push direction: take an Open Org profile (optionally with ideas) and
push relevant data INTO a CRM via its REST API. All HTTP is mocked — no
network access.

Covers:
* Field mapping functions (Beacon, Lamplight, Salesforce)
* ideas → campaigns / opportunities mappers
* push_profile_to_crm orchestrator for each CRM system
* Error handling and empty-list edge cases
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from llmstxt_core.open_org.crm_push import (
    ideas_to_beacon_campaigns,
    ideas_to_salesforce_opportunities,
    profile_to_beacon_constituent,
    profile_to_lamplight_profile,
    profile_to_salesforce_account,
    push_profile_to_crm,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_PROFILE_JSON = {
    "schema_version": "open-org/v0.1",
    "identity": {
        "name": "Riverside Community Trust",
        "registration": {
            "charity_commission_ew": "1234567",
        },
        "website": "https://riverside-trust.org.uk",
        "geography": {"primary_area": "Great Yarmouth"},
        "scale": {"annual_income_band": "250k-500k"},
    },
    "mission": {
        "summary": "Supporting isolated older people to build social connections.",
        "themes": ["older_people", "loneliness", "community_development"],
        "beneficiaries": ["Isolated older people"],
    },
    "ideas": [
        {
            "id": "community-kitchen-network",
            "status": "developing",
            "summary": "A network of three community kitchens across Great Yarmouth.",
            "themes": ["food_access", "community_development"],
            "indicative_cost": {
                "lower": 80000,
                "upper": 120000,
                "currency": "GBP",
                "period": "2 years",
            },
        },
        {
            "id": "befriending-calls",
            "status": "shaped",
            "summary": "Weekly phone befriending for housebound older people.",
            "themes": ["older_people", "loneliness"],
            "indicative_cost": {
                "lower": 15000,
                "upper": 30000,
                "currency": "GBP",
                "period": "year",
            },
        },
    ],
}

_PROFILE_NO_IDEAS = {
    "schema_version": "open-org/v0.1",
    "identity": {
        "name": "Small Charity",
        "registration": {"charity_commission_ew": "7654321"},
        "website": "https://small-charity.org",
    },
    "mission": {
        "summary": "Helping people.",
        "themes": ["education"],
    },
}

_IDEAS = _PROFILE_JSON["ideas"]


# ---------------------------------------------------------------------------
# HTTP mock helpers
# ---------------------------------------------------------------------------


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


# ===========================================================================
# profile_to_beacon_constituent
# ===========================================================================


def test_profile_to_beacon_constituent_maps_name():
    result = profile_to_beacon_constituent(_PROFILE_JSON)
    assert result["name"] == "Riverside Community Trust"


def test_profile_to_beacon_constituent_maps_charity_number_to_custom():
    result = profile_to_beacon_constituent(_PROFILE_JSON)
    assert result["custom_fields"]["charity_number"] == "1234567"


def test_profile_to_beacon_constituent_maps_themes_to_tags():
    result = profile_to_beacon_constituent(_PROFILE_JSON)
    assert result["tags"] == ["older_people", "loneliness", "community_development"]


def test_profile_to_beacon_constituent_maps_summary_to_description():
    result = profile_to_beacon_constituent(_PROFILE_JSON)
    assert result["description"] == "Supporting isolated older people to build social connections."


def test_profile_to_beacon_constituent_no_charity_number():
    profile = {
        "identity": {"name": "No Reg", "registration": {"companies_house": "123"}},
        "mission": {"themes": []},
    }
    result = profile_to_beacon_constituent(profile)
    assert "charity_number" not in result.get("custom_fields", {})


# ===========================================================================
# profile_to_lamplight_profile
# ===========================================================================


def test_profile_to_lamplight_profile_maps_name():
    result = profile_to_lamplight_profile(_PROFILE_JSON)
    assert result["name"] == "Riverside Community Trust"


def test_profile_to_lamplight_profile_maps_themes_to_service_tags():
    result = profile_to_lamplight_profile(_PROFILE_JSON)
    assert result["tags"] == ["older_people", "loneliness", "community_development"]


def test_profile_to_lamplight_profile_maps_ideas_to_work_records():
    result = profile_to_lamplight_profile(_PROFILE_JSON)
    assert isinstance(result["work_records"], list)
    assert len(result["work_records"]) == 2
    assert result["work_records"][0]["type"] == "community-kitchen-network"
    assert result["work_records"][0]["notes"] == "A network of three community kitchens across Great Yarmouth."


def test_profile_to_lamplight_profile_no_ideas():
    result = profile_to_lamplight_profile(_PROFILE_NO_IDEAS)
    assert result["work_records"] == []


# ===========================================================================
# profile_to_salesforce_account
# ===========================================================================


def test_profile_to_salesforce_account_maps_name():
    result = profile_to_salesforce_account(_PROFILE_JSON)
    assert result["Name"] == "Riverside Community Trust"


def test_profile_to_salesforce_account_maps_charity_number():
    result = profile_to_salesforce_account(_PROFILE_JSON)
    assert result["Charity_Number__c"] == "1234567"


def test_profile_to_salesforce_account_maps_website():
    result = profile_to_salesforce_account(_PROFILE_JSON)
    assert result["Website"] == "https://riverside-trust.org.uk"


def test_profile_to_salesforce_account_maps_topics():
    result = profile_to_salesforce_account(_PROFILE_JSON)
    assert result["Topics__c"] == "older_people;loneliness;community_development"


# ===========================================================================
# ideas_to_beacon_campaigns
# ===========================================================================


def test_ideas_to_beacon_campaigns_maps_list():
    result = ideas_to_beacon_campaigns(_IDEAS)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["name"] == "community-kitchen-network"
    assert result[0]["description"] == "A network of three community kitchens across Great Yarmouth."
    assert result[0]["status"] == "developing"


def test_ideas_to_beacon_campaigns_empty_list():
    result = ideas_to_beacon_campaigns([])
    assert result == []


# ===========================================================================
# ideas_to_salesforce_opportunities
# ===========================================================================


def test_ideas_to_salesforce_opportunities_maps_name_amount_stage():
    result = ideas_to_salesforce_opportunities(_IDEAS)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["Name"] == "community-kitchen-network"
    assert result[0]["Amount"] == 120000  # upper bound
    assert result[0]["StageName"] == "Developing"


def test_ideas_to_salesforce_opportunities_empty_list():
    result = ideas_to_salesforce_opportunities([])
    assert result == []


def test_ideas_to_salesforce_opportunities_no_cost_defaults_to_zero():
    ideas = [{"id": "free-idea", "status": "seed", "summary": "Free thing."}]
    result = ideas_to_salesforce_opportunities(ideas)
    assert result[0]["Amount"] == 0


# ===========================================================================
# push_profile_to_crm — Beacon
# ===========================================================================


@pytest.mark.asyncio
async def test_push_profile_to_beacon():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        side_effect=[
            _mock_response(201, {"id": "const-001", "name": "Riverside Community Trust"}),
            _mock_response(201, {"id": "camp-001"}),
            _mock_response(201, {"id": "camp-002"}),
        ]
    )

    result = await push_profile_to_crm(
        _PROFILE_JSON,
        crm_system="beacon",
        api_key="test-key",
        http_client_factory=lambda: mock_client,
    )

    assert result["system"] == "beacon"
    assert result["constituent_id"] == "const-001"
    assert result["campaigns_created"] == 2
    assert mock_client.post.await_count == 3


@pytest.mark.asyncio
async def test_push_profile_to_beacon_no_ideas():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        return_value=_mock_response(201, {"id": "const-999"})
    )

    result = await push_profile_to_crm(
        _PROFILE_NO_IDEAS,
        crm_system="beacon",
        api_key="test-key",
        http_client_factory=lambda: mock_client,
    )

    assert result["system"] == "beacon"
    assert result["constituent_id"] == "const-999"
    assert result["campaigns_created"] == 0
    assert mock_client.post.await_count == 1


# ===========================================================================
# push_profile_to_crm — Lamplight
# ===========================================================================


@pytest.mark.asyncio
async def test_push_profile_to_lamplight():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        side_effect=[
            _mock_response(201, {"id": "prof-001", "name": "Riverside Community Trust"}),
            _mock_response(201, {"id": "wr-001"}),
            _mock_response(201, {"id": "wr-002"}),
        ]
    )

    result = await push_profile_to_crm(
        _PROFILE_JSON,
        crm_system="lamplight",
        api_key="test-key",
        base_url="https://lamplight.example.org/api",
        http_client_factory=lambda: mock_client,
    )

    assert result["system"] == "lamplight"
    assert result["profile_id"] == "prof-001"
    assert result["work_records_created"] == 2
    assert mock_client.post.await_count == 3


# ===========================================================================
# push_profile_to_crm — Salesforce
# ===========================================================================


@pytest.mark.asyncio
async def test_push_profile_to_salesforce():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        side_effect=[
            _mock_response(201, {"id": "001ACCOUNT", "success": True}),
            _mock_response(201, {"id": "006OPP001", "success": True}),
            _mock_response(201, {"id": "006OPP002", "success": True}),
        ]
    )

    result = await push_profile_to_crm(
        _PROFILE_JSON,
        crm_system="salesforce",
        access_token="test-token",
        instance_url="https://riverside.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )

    assert result["system"] == "salesforce"
    assert result["account_id"] == "001ACCOUNT"
    assert result["opportunities_created"] == 2
    assert mock_client.post.await_count == 3


@pytest.mark.asyncio
async def test_push_profile_to_salesforce_no_ideas():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        return_value=_mock_response(201, {"id": "001ACC", "success": True})
    )

    result = await push_profile_to_crm(
        _PROFILE_NO_IDEAS,
        crm_system="salesforce",
        access_token="tok",
        instance_url="https://test.my.salesforce.com",
        http_client_factory=lambda: mock_client,
    )

    assert result["opportunities_created"] == 0
    assert mock_client.post.await_count == 1


# ===========================================================================
# push_profile_to_crm — error handling
# ===========================================================================


@pytest.mark.asyncio
async def test_push_profile_to_crm_unknown_system_raises():
    with pytest.raises(ValueError, match="unsupported crm_system"):
        await push_profile_to_crm(_PROFILE_JSON, crm_system="unknown", api_key="x")


@pytest.mark.asyncio
async def test_push_profile_to_beacon_http_error_propagates():
    mock_client = _build_mock_client()
    mock_client.post = AsyncMock(
        return_value=_mock_response(500, {"error": "server error"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await push_profile_to_crm(
            _PROFILE_JSON,
            crm_system="beacon",
            api_key="test-key",
            http_client_factory=lambda: mock_client,
        )