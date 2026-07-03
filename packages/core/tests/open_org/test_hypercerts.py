"""Tests for the Hypercerts integration module.

Hypercerts are on-chain impact-claim tokens (Ethereum/Optimism) representing
a discrete piece of work and impact. This module builds the claim data from
a verified evidence item, provides a mockable mint function, and fetches
hypercerts from the subgraph.

The on-chain interaction is abstracted behind a wallet interface so tests
never touch a real blockchain.
"""

import pytest
from unittest.mock import AsyncMock

from llmstxt_core.open_org.hypercerts import (
    HypercertClaim,
    build_claim,
    fetch_hypercerts_for_org,
    hypercert_to_evidence,
    mint_claim,
    validate_evidence_for_minting,
)


# ---------------------------------------------------------------------------
# HypercertClaim dataclass
# ---------------------------------------------------------------------------


def test_hypercert_claim_accepts_all_fields():
    claim = HypercertClaim(
        work_scope="Community food programme in Great Yarmouth",
        impact_scope="50 meals/day served, 3 new food hubs established",
        contributors=["GB-CHC-1234567", "Lamplight:org-123"],
        timeframe_start=20240101,
        timeframe_end=20241231,
        units=1000,
        evidence_ref="ev-abc123",
        org_id="GB-CHC-1234567",
    )
    assert claim.work_scope == "Community food programme in Great Yarmouth"
    assert claim.impact_scope == "50 meals/day served, 3 new food hubs established"
    assert claim.contributors == ["GB-CHC-1234567", "Lamplight:org-123"]
    assert claim.timeframe_start == 20240101
    assert claim.timeframe_end == 20241231
    assert claim.units == 1000
    assert claim.evidence_ref == "ev-abc123"


def test_hypercert_claim_defaults():
    claim = HypercertClaim(
        work_scope="Test work",
        impact_scope="Test impact",
        contributors=["GB-CHC-1234567"],
        timeframe_start=20240101,
        timeframe_end=20241231,
        units=100,
        evidence_ref="ev1",
        org_id="GB-CHC-1234567",
    )
    assert claim.token_id is None
    assert claim.transaction_hash is None
    assert claim.chain_id is None


# ---------------------------------------------------------------------------
# validate_evidence_for_minting
# ---------------------------------------------------------------------------


def test_validate_evidence_accepts_outcome_data_with_outcomes():
    """A valid evidence item (outcome_data with populated outcomes) passes."""
    evidence = {
        "evidence_id": "ev1",
        "title": "WEMWBS improvement",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "outcomes": [
            {"metric": "WEMWBS", "baseline": 42, "follow_up": 48, "change": 6, "n": 30},
        ],
    }
    result = validate_evidence_for_minting(evidence)
    assert result["valid"] is True


def test_validate_evidence_rejects_non_outcome_data_type():
    """Only outcome_data evidence can be minted — no aspirations."""
    evidence = {
        "evidence_id": "ev2",
        "title": "Annual report",
        "evidence_type": "annual_report",
        "date": "2024-03-31",
        "outcomes": [],
    }
    result = validate_evidence_for_minting(evidence)
    assert result["valid"] is False
    assert "outcome_data" in result["reason"]


def test_validate_evidence_rejects_empty_outcomes():
    """outcome_data with no outcomes array cannot be minted."""
    evidence = {
        "evidence_id": "ev3",
        "title": "Empty outcomes",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "outcomes": [],
    }
    result = validate_evidence_for_minting(evidence)
    assert result["valid"] is False
    assert "outcomes" in result["reason"].lower()


def test_validate_evidence_rejects_missing_outcomes_key():
    """outcome_data without an outcomes key cannot be minted."""
    evidence = {
        "evidence_id": "ev4",
        "title": "No outcomes key",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
    }
    result = validate_evidence_for_minting(evidence)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# build_claim
# ---------------------------------------------------------------------------


def test_build_claim_from_evidence_item():
    """build_claim constructs a HypercertClaim from a verified evidence item."""
    evidence = {
        "evidence_id": "ev-abc123",
        "title": "Community food programme",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "themes": ["food_access", "community_development"],
        "outcomes": [
            {"metric": "meals_served", "value": 18000, "description": "18,000 meals served"},
            {"metric": "new_hubs", "value": 3, "description": "3 new food hubs"},
        ],
    }
    claim = build_claim(evidence, org_id="GB-CHC-1234567")

    assert claim.work_scope is not None
    assert "Community food programme" in claim.work_scope
    assert claim.impact_scope is not None
    assert "18,000 meals" in claim.impact_scope or "18000" in claim.impact_scope
    assert "GB-CHC-1234567" in claim.contributors
    assert claim.evidence_ref == "ev-abc123"
    assert claim.org_id == "GB-CHC-1234567"


def test_build_claim_extracts_timeframe_from_date():
    """build_claim derives timeframe from the evidence date."""
    evidence = {
        "evidence_id": "ev1",
        "title": "Test",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "outcomes": [{"metric": "test", "value": 1}],
    }
    claim = build_claim(evidence, org_id="GB-CHC-1234567")
    # Timeframe should be YYYYMMDD format
    assert claim.timeframe_start == 20240101  # start of year
    assert claim.timeframe_end == 20241231  # end of year


def test_build_claim_includes_crm_provenance_in_contributors():
    """build_claim includes CRM source identity in contributors."""
    evidence = {
        "evidence_id": "ev1",
        "title": "Test",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "outcomes": [{"metric": "WEMWBS", "value": 48}],
        "source": {"crm": "lamplight", "profile_id": "lamp-123"},
    }
    claim = build_claim(evidence, org_id="GB-CHC-1234567")
    assert any("lamplight" in c.lower() for c in claim.contributors)


def test_build_claim_calculates_units_from_outcomes():
    """build_claim derives units from the outcomes (e.g. total beneficiaries)."""
    evidence = {
        "evidence_id": "ev1",
        "title": "Test",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "outcomes": [
            {"metric": "beneficiaries", "value": 150, "n": 150},
        ],
    }
    claim = build_claim(evidence, org_id="GB-CHC-1234567")
    assert claim.units > 0


# ---------------------------------------------------------------------------
# mint_claim (mocked — no real blockchain)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mint_claim_returns_token_id_and_tx_hash():
    """mint_claim submits a transaction and returns the token ID + tx hash."""
    claim = HypercertClaim(
        work_scope="Test work",
        impact_scope="Test impact",
        contributors=["GB-CHC-1234567"],
        timeframe_start=20240101,
        timeframe_end=20241231,
        units=100,
        evidence_ref="ev1",
        org_id="GB-CHC-1234567",
    )

    # Mock mint function — simulates the on-chain mint
    mock_mint_fn = AsyncMock(return_value={
        "token_id": "123456789",
        "transaction_hash": "0xabc123def456",
        "chain_id": 10,  # Optimism
    })

    result = await mint_claim(claim, mint_fn=mock_mint_fn)

    assert result["token_id"] == "123456789"
    assert result["transaction_hash"] == "0xabc123def456"
    assert result["chain_id"] == 10
    assert result["success"] is True


@pytest.mark.asyncio
async def test_mint_claim_handles_failure():
    """mint_claim returns success=False when the mint function fails."""
    claim = HypercertClaim(
        work_scope="Test",
        impact_scope="Test",
        contributors=["GB-CHC-1234567"],
        timeframe_start=20240101,
        timeframe_end=20241231,
        units=100,
        evidence_ref="ev1",
        org_id="GB-CHC-1234567",
    )

    mock_mint_fn = AsyncMock(side_effect=Exception("gas estimation failed"))

    result = await mint_claim(claim, mint_fn=mock_mint_fn)

    assert result["success"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# fetch_hypercerts_for_org (mocked subgraph query)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_hypercerts_for_org_returns_hypercerts():
    """fetch_hypercerts_for_org queries the subgraph and returns token records."""
    mock_query_fn = AsyncMock(return_value=[
        {
            "token_id": "111",
            "claim_hash": "0xaaa",
            "work_scope": "Food programme",
            "impact_scope": "18,000 meals served",
            "units": "1000",
            "contributors": ["GB-CHC-1234567"],
            "timeframe_start": "20240101",
            "timeframe_end": "20241231",
            "transaction_hash": "0xbbb",
            "chain_id": 10,
        },
    ])

    results = await fetch_hypercerts_for_org(
        "GB-CHC-1234567",
        query_fn=mock_query_fn,
    )

    assert len(results) == 1
    assert results[0]["token_id"] == "111"
    assert results[0]["work_scope"] == "Food programme"


@pytest.mark.asyncio
async def test_fetch_hypercerts_for_org_empty_results():
    """fetch_hypercerts_for_org returns empty list when no hypercerts exist."""
    mock_query_fn = AsyncMock(return_value=[])
    results = await fetch_hypercerts_for_org("GB-CHC-1234567", query_fn=mock_query_fn)
    assert results == []


@pytest.mark.asyncio
async def test_fetch_hypercerts_for_org_handles_error():
    """fetch_hypercerts_for_org returns empty list on query error."""
    mock_query_fn = AsyncMock(side_effect=Exception("subgraph timeout"))
    results = await fetch_hypercerts_for_org("GB-CHC-1234567", query_fn=mock_query_fn)
    assert results == []


# ---------------------------------------------------------------------------
# hypercert_to_evidence
# ---------------------------------------------------------------------------


def test_hypercert_to_evidence_maps_token_to_evidence_item():
    """hypercert_to_evidence maps an on-chain hypercert back to an evidence[] item."""
    hypercert = {
        "token_id": "111",
        "claim_hash": "0xaaa",
        "work_scope": "Food programme",
        "impact_scope": "18,000 meals served",
        "units": "1000",
        "contributors": ["GB-CHC-1234567"],
        "timeframe_start": "20240101",
        "timeframe_end": "20241231",
        "transaction_hash": "0xbbb",
        "chain_id": 10,
    }
    item = hypercert_to_evidence(hypercert)

    assert item["evidence_type"] == "outcome_data"
    assert item["title"] is not None
    assert "Food programme" in item["title"]
    assert item["url"] is not None
    assert "hypercert" in item["url"].lower() or "111" in item["url"]
    assert item.get("hypercert") is not None
    assert item["hypercert"]["token_id"] == "111"
    assert item["hypercert"]["chain_id"] == 10


def test_hypercert_to_evidence_includes_outcomes():
    """hypercert_to_evidence includes the impact scope as an outcome."""
    hypercert = {
        "token_id": "222",
        "work_scope": "Test",
        "impact_scope": "50 beneficiaries helped",
        "units": "50",
        "contributors": ["GB-CHC-1234567"],
        "timeframe_start": "20240101",
        "timeframe_end": "20241231",
    }
    item = hypercert_to_evidence(hypercert)
    assert len(item["outcomes"]) > 0
    assert "50 beneficiaries" in item["outcomes"][0]["description"]