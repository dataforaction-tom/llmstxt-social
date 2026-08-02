"""Tests for the Hypercerts REST API routes.

Admin:  POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert
Public: GET  /open-org/{org_id}/hypercerts
Public: GET  /open-org/{org_id}/hypercerts/{token_id}

Tests call the route functions directly with a mocked DB session, following
the pattern in test_open_org_murmurations_route.py.
"""

from __future__ import annotations

import json
import uuid
from unittest import mock

import pytest


ORG_ID = "GB-CHC-1234567"
EVIDENCE_ID = "ev-outcome-001"


# --- helpers ----------------------------------------------------------------


def _profile_json(*, evidence=None):
    """Build a minimal valid profile_json dict with optional evidence items."""
    return {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": "Acme Aid",
            "identifiers": {"org_id": ORG_ID},
            "geography": {"primary_area": "Manchester"},
        },
        "mission": {"themes": ["education"]},
        "evidence": evidence if evidence is not None else [],
    }


def _valid_evidence():
    """Evidence item eligible for minting (outcome_data with outcomes)."""
    return {
        "evidence_id": EVIDENCE_ID,
        "title": "Literacy programme outcomes 2024",
        "evidence_type": "outcome_data",
        "date": "2024-06-15",
        "themes": ["education", "literacy"],
        "outcomes": [
            {"metric": "beneficiaries", "description": "120 adults completed", "n": 120},
        ],
        "source": {"crm": "beacon", "profile_id": "rec-123"},
    }


def _invalid_evidence():
    """Evidence item NOT eligible for minting (aspiration, no outcomes)."""
    return {
        "evidence_id": "ev-asp-001",
        "title": "We aspire to help",
        "evidence_type": "aspiration",
        "date": "2024-01-01",
        "themes": ["education"],
        "outcomes": [],
    }


def _profile(*, profile_json=None, published=True):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id=ORG_ID,
        published=published,
        profile_json=profile_json if profile_json is not None else _profile_json(),
    )


def _db_returning_one(result):
    """Build an async session whose .execute() returns a single scalar result."""
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=result)
    )
    return db


def _fake_admin():
    admin = mock.MagicMock()
    admin.user_id = uuid.uuid4()
    admin.org_id = ORG_ID
    admin.role = "owner"
    return admin


async def _mock_mint_fn(claim):
    """Mock mint function returning a fake on-chain result."""
    return {
        "token_id": "123456789",
        "transaction_hash": "0xabcdef1234567890",
        "chain_id": 10,
    }


# ---------------------------------------------------------------------------
# POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert (admin)
# ---------------------------------------------------------------------------


async def test_mint_hypercert_success():
    """Full pipeline: published profile + valid evidence → mint + write-back."""
    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    ev = _valid_evidence()
    profile = _profile(profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)
    admin = _fake_admin()

    result = await mint_hypercert(
        ORG_ID, EVIDENCE_ID, db=db, admin=admin, mint_fn=_mock_mint_fn
    )

    assert result["success"] is True
    assert result["token_id"] == "123456789"
    assert result["transaction_hash"] == "0xabcdef1234567890"
    assert result["chain_id"] == 10

    # The evidence item should now carry a hypercert reference.
    updated_ev = profile.profile_json["evidence"][0]
    assert "hypercert" in updated_ev
    assert updated_ev["hypercert"]["token_id"] == "123456789"
    assert updated_ev["hypercert"]["chain_id"] == 10
    assert updated_ev["hypercert"]["transaction_hash"] == "0xabcdef1234567890"

    # DB commit was called.
    db.commit.assert_awaited_once()


async def test_mint_hypercert_regenerates_markdown_source():
    """After minting, markdown_source must be regenerated from the updated profile_json.

    Without this, the editor silently wipes the hypercert reference on next save
    (same fix applied to the MCP tool). The converter doesn't render the
    ``hypercert`` subfield in markdown body text, but regenerating
    markdown_source from the updated JSON keeps the two DB columns consistent
    so the next editor fetch sees current content.
    """
    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    ev = _valid_evidence()
    profile = _profile(profile_json=_profile_json(evidence=[ev]))
    profile.markdown_source = "# old markdown without hypercert"
    db = _db_returning_one(profile)
    admin = _fake_admin()

    await mint_hypercert(ORG_ID, EVIDENCE_ID, db=db, admin=admin, mint_fn=_mock_mint_fn)

    # markdown_source should have changed (regenerated from updated_json).
    assert profile.markdown_source != "# old markdown without hypercert"
    # The regenerated markdown should reflect the current profile_json —
    # the evidence title appears in the rendered Evidence section.
    assert "Literacy programme outcomes 2024" in profile.markdown_source
    # And the profile_json (the DB source of truth) carries the hypercert ref.
    assert profile.profile_json["evidence"][0]["hypercert"]["token_id"] == "123456789"


async def test_mint_hypercert_404_when_profile_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    db = _db_returning_one(None)
    admin = _fake_admin()

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, EVIDENCE_ID, db=db, admin=admin, mint_fn=_mock_mint_fn
        )
    assert exc.value.status_code == 404


async def test_mint_hypercert_404_when_profile_has_no_content():
    """Published profile with profile_json=None → 404."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    profile = _profile(published=True)
    profile.profile_json = None
    db = _db_returning_one(profile)
    admin = _fake_admin()

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, EVIDENCE_ID, db=db, admin=admin, mint_fn=_mock_mint_fn
        )
    assert exc.value.status_code == 404


async def test_mint_hypercert_404_when_evidence_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    profile = _profile(profile_json=_profile_json(evidence=[_invalid_evidence()]))
    db = _db_returning_one(profile)
    admin = _fake_admin()

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, "nonexistent-ev", db=db, admin=admin, mint_fn=_mock_mint_fn
        )
    assert exc.value.status_code == 404


async def test_mint_hypercert_400_when_evidence_not_valid_for_minting():
    """Aspiration-type evidence (no outcomes) → 400."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    ev = _invalid_evidence()
    profile = _profile(profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)
    admin = _fake_admin()

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, ev["evidence_id"], db=db, admin=admin, mint_fn=_mock_mint_fn
        )
    assert exc.value.status_code == 400


async def test_mint_hypercert_400_when_outcome_data_has_no_outcomes():
    """outcome_data evidence with empty outcomes[] → 400."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    ev = {
        "evidence_id": "ev-empty-001",
        "title": "Empty outcomes",
        "evidence_type": "outcome_data",
        "date": "2024-01-01",
        "outcomes": [],
    }
    profile = _profile(profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)
    admin = _fake_admin()

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, ev["evidence_id"], db=db, admin=admin, mint_fn=_mock_mint_fn
        )
    assert exc.value.status_code == 400


async def test_mint_hypercert_502_when_mint_fn_fails():
    """If the mint_fn raises, the route returns 502."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import mint_hypercert

    ev = _valid_evidence()
    profile = _profile(profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)
    admin = _fake_admin()

    async def _failing_mint_fn(claim):
        raise RuntimeError("wallet connection refused")

    with pytest.raises(HTTPException) as exc:
        await mint_hypercert(
            ORG_ID, EVIDENCE_ID, db=db, admin=admin, mint_fn=_failing_mint_fn
        )
    assert exc.value.status_code == 502


# ---------------------------------------------------------------------------
# GET /open-org/{org_id}/hypercerts (public)
# ---------------------------------------------------------------------------


async def test_list_hypercerts_returns_empty_array_when_none_minted():
    from llmstxt_api.routes.open_org_hypercerts import list_hypercerts

    profile = _profile(published=True, profile_json=_profile_json(evidence=[_valid_evidence()]))
    db = _db_returning_one(profile)

    response = await list_hypercerts(ORG_ID, db)
    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body == []


async def test_list_hypercerts_returns_hypercert_summaries():
    from llmstxt_api.routes.open_org_hypercerts import list_hypercerts

    ev1 = _valid_evidence()
    ev1["hypercert"] = {
        "token_id": "tok-1",
        "chain_id": 10,
        "transaction_hash": "0xabc",
    }
    ev2 = _valid_evidence()
    ev2["evidence_id"] = "ev-outcome-002"
    ev2["title"] = "Second outcome"
    ev2["hypercert"] = {
        "token_id": "tok-2",
        "chain_id": 10,
        "transaction_hash": "0xdef",
    }
    profile = _profile(published=True, profile_json=_profile_json(evidence=[ev1, ev2]))
    db = _db_returning_one(profile)

    response = await list_hypercerts(ORG_ID, db)
    body = json.loads(response.body)
    assert len(body) == 2
    assert body[0]["token_id"] == "tok-1"
    assert body[0]["evidence_id"] == EVIDENCE_ID
    assert body[1]["token_id"] == "tok-2"
    assert body[1]["evidence_id"] == "ev-outcome-002"


async def test_list_hypercerts_skips_evidence_without_hypercert_field():
    """Only evidence items that have a ``hypercert`` dict are included."""
    from llmstxt_api.routes.open_org_hypercerts import list_hypercerts

    ev_with = _valid_evidence()
    ev_with["hypercert"] = {"token_id": "tok-1", "chain_id": 10, "transaction_hash": "0xabc"}
    ev_without = _valid_evidence()
    ev_without["evidence_id"] = "ev-no-hc-001"
    profile = _profile(
        published=True,
        profile_json=_profile_json(evidence=[ev_with, ev_without]),
    )
    db = _db_returning_one(profile)

    response = await list_hypercerts(ORG_ID, db)
    body = json.loads(response.body)
    assert len(body) == 1
    assert body[0]["token_id"] == "tok-1"


async def test_list_hypercerts_404_when_profile_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import list_hypercerts

    db = _db_returning_one(None)
    with pytest.raises(HTTPException) as exc:
        await list_hypercerts(ORG_ID, db)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /open-org/{org_id}/hypercerts/{token_id} (public)
# ---------------------------------------------------------------------------


async def test_get_hypercert_returns_detail():
    from llmstxt_api.routes.open_org_hypercerts import get_hypercert

    ev = _valid_evidence()
    ev["hypercert"] = {
        "token_id": "tok-42",
        "chain_id": 10,
        "transaction_hash": "0xabc123",
    }
    profile = _profile(published=True, profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)

    response = await get_hypercert(ORG_ID, "tok-42", db)
    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body["hypercert"]["token_id"] == "tok-42"
    assert body["evidence_id"] == EVIDENCE_ID
    assert body["title"] == ev["title"]
    assert body["evidence_type"] == "outcome_data"
    assert "outcomes" in body


async def test_get_hypercert_404_when_token_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import get_hypercert

    ev = _valid_evidence()
    ev["hypercert"] = {"token_id": "tok-42", "chain_id": 10, "transaction_hash": "0xabc"}
    profile = _profile(published=True, profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)

    with pytest.raises(HTTPException) as exc:
        await get_hypercert(ORG_ID, "nonexistent-token", db)
    assert exc.value.status_code == 404


async def test_get_hypercert_404_when_profile_not_found():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_hypercerts import get_hypercert

    db = _db_returning_one(None)
    with pytest.raises(HTTPException) as exc:
        await get_hypercert(ORG_ID, "tok-42", db)
    assert exc.value.status_code == 404


async def test_get_hypercert_matches_token_id_as_string():
    """token_id from the URL is a string; the stored value might be int or str."""
    from llmstxt_api.routes.open_org_hypercerts import get_hypercert

    ev = _valid_evidence()
    ev["hypercert"] = {
        "token_id": 99999,  # stored as int in the JSON
        "chain_id": 10,
        "transaction_hash": "0xabc",
    }
    profile = _profile(published=True, profile_json=_profile_json(evidence=[ev]))
    db = _db_returning_one(profile)

    response = await get_hypercert(ORG_ID, "99999", db)
    body = json.loads(response.body)
    assert body["hypercert"]["token_id"] == 99999