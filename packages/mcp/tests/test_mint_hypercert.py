"""Tests for the MCP mint_hypercert admin tool.

The mint_hypercert tool wraps the hypercerts module: validates the evidence
item, builds the claim, and submits via an injectable mint function.
Minting is irreversible (on-chain) so the tool requires explicit confirmation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openorg_mcp.admin_tools import mint_hypercert
from llmstxt_core.open_org.hypercerts import HypercertClaim


# ---------------------------------------------------------------------------
# mint_hypercert — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mint_hypercert_returns_token_id_on_success():
    """mint_hypercert validates evidence, builds claim, and returns token ID."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {
        "evidence": [
            {
                "evidence_id": "ev-abc",
                "title": "Community food programme",
                "evidence_type": "outcome_data",
                "date": "2024-06-15",
                "themes": ["food_access"],
                "outcomes": [
                    {"metric": "meals_served", "value": 18000, "description": "18,000 meals served"},
                ],
            }
        ]
    }
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    mock_mint_fn = AsyncMock(return_value={
        "token_id": "999",
        "transaction_hash": "0xdeadbeef",
        "chain_id": 10,
    })

    result = await mint_hypercert(
        db,
        org_id="GB-CHC-1234567",
        evidence_id="ev-abc",
        mint_fn=mock_mint_fn,
    )

    assert result["success"] is True
    assert result["token_id"] == "999"
    assert result["transaction_hash"] == "0xdeadbeef"
    # Evidence item should be updated with hypercert reference
    assert "evidence" in result
    ev = [e for e in result["evidence"] if e["evidence_id"] == "ev-abc"][0]
    assert ev.get("hypercert") is not None
    assert ev["hypercert"]["token_id"] == "999"


@pytest.mark.asyncio
async def test_mint_hypercert_rejects_non_outcome_data():
    """mint_hypercert refuses to mint evidence that isn't outcome_data."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {
        "evidence": [
            {
                "evidence_id": "ev-bad",
                "title": "Annual report",
                "evidence_type": "annual_report",
                "date": "2024-03-31",
                "outcomes": [],
            }
        ]
    }
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await mint_hypercert(
        db,
        org_id="GB-CHC-1234567",
        evidence_id="ev-bad",
        mint_fn=AsyncMock(),
    )

    assert result["success"] is False
    assert "outcome_data" in result["error"]


@pytest.mark.asyncio
async def test_mint_hypercert_rejects_evidence_not_found():
    """mint_hypercert fails if the evidence_id is not found in the profile."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {"evidence": []}
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    result = await mint_hypercert(
        db,
        org_id="GB-CHC-1234567",
        evidence_id="ev-missing",
        mint_fn=AsyncMock(),
    )

    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_mint_hypercert_rejects_unpublished_org():
    """mint_hypercert fails if the org is not found or unpublished."""
    db = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=profile_result)

    result = await mint_hypercert(
        db,
        org_id="GB-CHC-9999999",
        evidence_id="ev-abc",
        mint_fn=AsyncMock(),
    )

    assert result["success"] is False


@pytest.mark.asyncio
async def test_mint_hypercert_handles_mint_failure():
    """mint_hypercert returns failure when the on-chain mint fails."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {
        "evidence": [
            {
                "evidence_id": "ev-ok",
                "title": "Valid outcome",
                "evidence_type": "outcome_data",
                "date": "2024-06-15",
                "outcomes": [{"metric": "test", "value": 100, "n": 100}],
            }
        ]
    }
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    mock_mint_fn = AsyncMock(side_effect=Exception("gas estimation failed"))

    result = await mint_hypercert(
        db,
        org_id="GB-CHC-1234567",
        evidence_id="ev-ok",
        mint_fn=mock_mint_fn,
    )

    assert result["success"] is False
    assert "gas" in result["error"].lower() or "error" in result["error"].lower()


@pytest.mark.asyncio
async def test_mint_hypercert_commits_to_db():
    """mint_hypercert commits the updated evidence (with hypercert ref) to DB."""
    db = AsyncMock()

    profile = MagicMock()
    profile.profile_json = {
        "evidence": [
            {
                "evidence_id": "ev-commit",
                "title": "Test",
                "evidence_type": "outcome_data",
                "date": "2024-06-15",
                "outcomes": [{"metric": "x", "value": 1, "n": 1}],
            }
        ]
    }
    profile.published = True
    profile_result = MagicMock()
    profile_result.scalars.return_value.one_or_none.return_value = profile
    db.execute = AsyncMock(return_value=profile_result)

    mock_mint_fn = AsyncMock(return_value={
        "token_id": "42",
        "transaction_hash": "0xabc",
        "chain_id": 10,
    })

    await mint_hypercert(
        db,
        org_id="GB-CHC-1234567",
        evidence_id="ev-commit",
        mint_fn=mock_mint_fn,
    )

    db.commit.assert_awaited()