"""Tests for MCP admin tools (sync_from_crm, add_evidence).

Admin tools require an org admin token for authentication. These tests
mock the DB session and CRM clients — no real Postgres or CRM API access.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openorg_mcp.admin_tools import (
    add_evidence,
    sync_from_crm,
    validate_admin_token,
)


# ---------------------------------------------------------------------------
# validate_admin_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_admin_token_returns_true_for_valid_token():
    """A valid admin token for the org passes validation."""
    db = AsyncMock()
    # Mock: the query returns a row meaning the user is an admin of this org
    result = MagicMock()
    result.scalar.return_value = True
    db.execute = AsyncMock(return_value=result)
    valid = await validate_admin_token(db, org_id="GB-CHC-1234567", token="valid-token")
    assert valid is True


@pytest.mark.asyncio
async def test_validate_admin_token_returns_false_for_invalid_token():
    """An invalid/expired token fails validation."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = None  # No admin row found
    db.execute = AsyncMock(return_value=result)
    valid = await validate_admin_token(db, org_id="GB-CHC-1234567", token="bad-token")
    assert valid is False


@pytest.mark.asyncio
async def test_validate_admin_token_returns_false_for_none_token():
    """A None token fails validation without hitting the DB."""
    db = AsyncMock()
    valid = await validate_admin_token(db, org_id="GB-CHC-1234567", token=None)
    assert valid is False
    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# sync_from_crm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_from_crm_beacon_returns_evidence_items():
    """sync_from_crm with Beacon CRM returns donations + cases as evidence."""
    db = AsyncMock()

    # Mock profile lookup
    profile = MagicMock()
    profile.profile_json = {"identity": {"name": "Test Org"}, "evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    from llmstxt_core.enrichers.beacon_crm import BeaconDonation, BeaconCase

    # Mock Beacon client
    mock_beacon = AsyncMock()
    mock_beacon.get_donations = AsyncMock(return_value=[
        BeaconDonation(id="d1", amount=5000, currency="GBP", date="2024-01-01",
                       fund="General", campaign="Winter Appeal"),
    ])
    mock_beacon.get_cases = AsyncMock(return_value=[
        BeaconCase(id="c1", title="Case A", status="open",
                   opened_date="2024-02-01", closed_date=None, description="desc"),
    ])

    with patch("openorg_mcp.admin_tools.BeaconClient", return_value=mock_beacon):
        result = await sync_from_crm(
            db,
            org_id="GB-CHC-1234567",
            crm_system="beacon",
            crm_api_key="test-key",
            constituent_id="const-1",
        )

    assert "evidence_items" in result
    assert len(result["evidence_items"]) >= 1
    assert "profile_updated" in result


@pytest.mark.asyncio
async def test_sync_from_crm_lamplight_returns_outcome_evidence():
    """sync_from_crm with Lamplight returns outcome measurements as evidence."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"identity": {"name": "Test Org"}, "evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    from llmstxt_core.enrichers.lamplight_crm import LamplightOutcome

    mock_lamplight = AsyncMock()
    mock_lamplight.get_outcomes = AsyncMock(return_value=[
        LamplightOutcome(outcome_id="o1", person_id="p1", measurement_type="WEMWBS",
                         value=42, date="2024-01-15", notes="baseline"),
        LamplightOutcome(outcome_id="o2", person_id="p1", measurement_type="WEMWBS",
                         value=48, date="2024-06-15", notes="follow-up"),
    ])
    mock_lamplight.get_work_records = AsyncMock(return_value=[])

    with patch("openorg_mcp.admin_tools.LamplightClient", return_value=mock_lamplight):
        result = await sync_from_crm(
            db,
            org_id="GB-CHC-1234567",
            crm_system="lamplight",
            crm_api_key="test-key",
            profile_id="lamp-1",
        )

    assert len(result["evidence_items"]) >= 1
    assert result["evidence_items"][0]["evidence_type"] == "outcome_data"


@pytest.mark.asyncio
async def test_sync_from_crm_salesforce_returns_grant_evidence():
    """sync_from_crm with Salesforce returns grants as evidence."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"identity": {"name": "Test Org"}, "evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    from llmstxt_core.enrichers.salesforce_crm import SalesforceOpportunity

    mock_sf = AsyncMock()
    mock_sf.get_opportunities = AsyncMock(return_value=[
        SalesforceOpportunity(id="opp1", name="Big Grant", amount=50000, stage="Closed Won",
                              close_date="2024-03-01", type="Grant", account_id="acc1"),
    ])
    mock_sf.get_contacts = AsyncMock(return_value=[])

    with patch("openorg_mcp.admin_tools.SalesforceClient", return_value=mock_sf):
        result = await sync_from_crm(
            db,
            org_id="GB-CHC-1234567",
            crm_system="salesforce",
            access_token="test-token",
            instance_url="https://test.my.salesforce.com",
            account_id="acc1",
        )

    assert len(result["evidence_items"]) >= 1
    assert result["evidence_items"][0]["evidence_type"] == "outcome_data"


@pytest.mark.asyncio
async def test_sync_from_crm_returns_error_for_unpublished_org():
    """sync_from_crm fails if the org profile is unpublished."""
    db = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=profile_result)

    result = await sync_from_crm(
        db,
        org_id="GB-CHC-1234567",
        crm_system="beacon",
        crm_api_key="test-key",
        constituent_id="const-1",
    )

    assert "error" in result
    assert "not found" in result["error"].lower() or "unpublished" in result["error"].lower()


@pytest.mark.asyncio
async def test_sync_from_crm_returns_error_for_unknown_crm():
    """sync_from_crm fails for an unsupported CRM system."""
    db = AsyncMock()
    profile = MagicMock()
    profile.profile_json = {"evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await sync_from_crm(
        db,
        org_id="GB-CHC-1234567",
        crm_system="unknown_crm",
        crm_api_key="test-key",
    )

    assert "error" in result
    assert "unknown" in result["error"].lower() or "unsupported" in result["error"].lower()


@pytest.mark.asyncio
async def test_sync_from_crm_does_not_duplicate_existing_evidence():
    """sync_from_crm filters out evidence items that already exist by title+date."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {
        "evidence": [
            {"evidence_id": "existing-1", "title": "Big Grant", "date": "2024-03-01",
             "evidence_type": "outcome_data"}
        ]
    }
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    from llmstxt_core.enrichers.salesforce_crm import SalesforceOpportunity

    mock_sf = AsyncMock()
    mock_sf.get_opportunities = AsyncMock(return_value=[
        SalesforceOpportunity(id="opp1", name="Big Grant", amount=50000, stage="Closed Won",
                              close_date="2024-03-01", type="Grant", account_id="acc1"),
        SalesforceOpportunity(id="opp2", name="New Grant", amount=10000, stage="Closed Won",
                              close_date="2024-05-01", type="Grant", account_id="acc1"),
    ])
    mock_sf.get_contacts = AsyncMock(return_value=[])

    with patch("openorg_mcp.admin_tools.SalesforceClient", return_value=mock_sf):
        result = await sync_from_crm(
            db,
            org_id="GB-CHC-1234567",
            crm_system="salesforce",
            access_token="test-token",
            instance_url="https://test.my.salesforce.com",
            account_id="acc1",
        )

    # Only the new grant should be in evidence_items (existing one filtered out)
    titles = [e["title"] for e in result["evidence_items"]]
    assert "New Grant" in titles
    assert "Big Grant" not in titles


# ---------------------------------------------------------------------------
# add_evidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_evidence_appends_to_profile_json():
    """add_evidence appends a new evidence item to the profile's evidence[] array."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"identity": {"name": "Test"}, "evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    new_item = {
        "title": "New evidence",
        "evidence_type": "external_research",
        "date": "2024-06-01",
        "url": "https://example.com/study",
        "themes": ["food_access"],
        "outcomes": [],
    }

    result = await add_evidence(db, org_id="GB-CHC-1234567", evidence_item=new_item)

    assert result["success"] is True
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["title"] == "New evidence"
    assert "evidence_id" in result["evidence"][0]
    # DB was updated
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_add_evidence_generates_evidence_id():
    """add_evidence auto-generates an evidence_id if not provided."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await add_evidence(
        db,
        org_id="GB-CHC-1234567",
        evidence_item={"title": "Test", "evidence_type": "case_study", "date": "2024-01-01"},
    )

    assert result["evidence"][0]["evidence_id"] is not None
    assert len(result["evidence"][0]["evidence_id"]) > 0


@pytest.mark.asyncio
async def test_add_evidence_preserves_existing_items():
    """add_evidence appends without removing existing evidence items."""
    db = AsyncMock()

    existing = {"evidence_id": "ev1", "title": "Old", "evidence_type": "annual_report", "date": "2023-01-01"}
    profile = MagicMock()
    profile.profile_json = {"evidence": [existing]}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await add_evidence(
        db,
        org_id="GB-CHC-1234567",
        evidence_item={"title": "New", "evidence_type": "case_study", "date": "2024-06-01"},
    )

    assert len(result["evidence"]) == 2
    titles = [e["title"] for e in result["evidence"]]
    assert "Old" in titles
    assert "New" in titles


@pytest.mark.asyncio
async def test_add_evidence_returns_error_for_unpublished_org():
    """add_evidence fails if the org is not found or unpublished."""
    db = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=profile_result)

    result = await add_evidence(
        db,
        org_id="GB-CHC-9999999",
        evidence_item={"title": "Test", "evidence_type": "case_study", "date": "2024-01-01"},
    )

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_add_evidence_rejects_invalid_evidence_type():
    """add_evidence rejects an evidence item with an invalid evidence_type."""
    db = AsyncMock()
    profile = MagicMock()
    profile.profile_json = {"evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await add_evidence(
        db,
        org_id="GB-CHC-1234567",
        evidence_item={"title": "Bad", "evidence_type": "not_a_real_type", "date": "2024-01-01"},
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_add_evidence_rejects_missing_title():
    """add_evidence rejects an item without a title."""
    db = AsyncMock()
    profile = MagicMock()
    profile.profile_json = {"evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await add_evidence(
        db,
        org_id="GB-CHC-1234567",
        evidence_item={"evidence_type": "case_study", "date": "2024-01-01"},
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_add_evidence_updates_markdown_source():
    """add_evidence regenerates markdown_source alongside profile_json.

    The markdown editor treats markdown_source as canonical — on every PUT
    it regenerates profile_json from the markdown. If add_evidence only
    updates profile_json, the next editor save silently wipes the MCP-added
    evidence. This test verifies markdown_source is kept in sync.
    """
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"identity": {"name": "Test Org"}, "evidence": []}
    profile.markdown_source = "---\nidentity:\n  name: Test Org\n---\n"
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    new_item = {
        "title": "New evidence",
        "evidence_type": "external_research",
        "date": "2024-06-01",
        "url": "https://example.com/study",
        "themes": ["food_access"],
        "outcomes": [],
    }

    result = await add_evidence(db, org_id="GB-CHC-1234567", evidence_item=new_item)

    assert result["success"] is True
    # markdown_source must have been updated to include the new evidence
    assert profile.markdown_source is not None
    assert "New evidence" in profile.markdown_source
    assert "external_research" in profile.markdown_source