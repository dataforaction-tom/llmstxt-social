"""Tests for the Lamplight CRM enricher.

Lamplight is a UK service-delivery CRM where outcomes are core data
(WEMWBS, Outcome Stars, custom measurements tracked over time). The API
is gated behind paid add-on modules (Publishing Module for writes,
Data Connect for a read-only OData feed). This module builds a client
abstraction against the Data Connect feed pattern, with mockable HTTP.

Tests mock all HTTP — no network access.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llmstxt_core.enrichers.lamplight_crm import (
    LamplightClient,
    LamplightOutcome,
    LamplightProfile,
    LamplightWorkRecord,
    outcomes_to_evidence,
    work_records_to_evidence,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_lamplight_outcome_accepts_all_fields():
    o = LamplightOutcome(
        outcome_id="out-1",
        person_id="person-42",
        measurement_type="WEMWBS",
        value=52,
        date="2024-03-15",
        notes="Baseline assessment",
    )
    assert o.outcome_id == "out-1"
    assert o.person_id == "person-42"
    assert o.measurement_type == "WEMWBS"
    assert o.value == 52
    assert o.date == "2024-03-15"
    assert o.notes == "Baseline assessment"


def test_lamplight_work_record_accepts_all_fields():
    w = LamplightWorkRecord(
        record_id="work-1",
        person_id="person-42",
        type="1-2-1 session",
        date="2024-04-01",
        project="Befriending",
        notes="Initial befriending session",
    )
    assert w.record_id == "work-1"
    assert w.person_id == "person-42"
    assert w.type == "1-2-1 session"
    assert w.date == "2024-04-01"
    assert w.project == "Befriending"
    assert w.notes == "Initial befriending session"


def test_lamplight_profile_accepts_all_fields():
    outcomes = [
        LamplightOutcome("out-1", "person-42", "WEMWBS", 40, "2024-01-01", None),
    ]
    work_records = [
        LamplightWorkRecord("work-1", "person-42", "session", "2024-01-05", "Proj", None),
    ]
    p = LamplightProfile(
        profile_id="person-42",
        name="Alex Sample",
        tags=["befriending", "mental-health"],
        outcomes=outcomes,
        work_records=work_records,
    )
    assert p.profile_id == "person-42"
    assert p.name == "Alex Sample"
    assert p.tags == ["befriending", "mental-health"]
    assert len(p.outcomes) == 1
    assert len(p.work_records) == 1
    assert p.outcomes[0].outcome_id == "out-1"
    assert p.work_records[0].record_id == "work-1"


# ---------------------------------------------------------------------------
# API response fixtures
# ---------------------------------------------------------------------------

_PROFILE_RESPONSE = {
    "id": "person-42",
    "name": "Alex Sample",
    "tags": ["befriending", "mental-health"],
}

_OUTCOMES_RESPONSE = {
    "value": [
        {
            "id": "out-1",
            "person_id": "person-42",
            "measurement_type": "WEMWBS",
            "value": 40,
            "date": "2024-01-01",
            "notes": "Baseline",
        },
        {
            "id": "out-2",
            "person_id": "person-42",
            "measurement_type": "WEMWBS",
            "value": 56,
            "date": "2024-06-01",
            "notes": "Follow-up",
        },
        {
            "id": "out-3",
            "person_id": "person-42",
            "measurement_type": "OUTCOME_STAR",
            "value": 3,
            "date": "2024-01-05",
            "notes": None,
        },
        {
            "id": "out-4",
            "person_id": "person-42",
            "measurement_type": "OUTCOME_STAR",
            "value": 7,
            "date": "2024-06-05",
            "notes": None,
        },
    ],
}

_WORK_RECORDS_RESPONSE = {
    "value": [
        {
            "id": "work-1",
            "person_id": "person-42",
            "type": "1-2-1 session",
            "date": "2024-04-01",
            "project": "Befriending",
            "notes": "Initial session",
        },
        {
            "id": "work-2",
            "person_id": "person-42",
            "type": "Group activity",
            "date": "2024-04-15",
            "project": "Befriending",
            "notes": None,
        },
    ],
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


def _mock_httpx_client(resp: MagicMock) -> AsyncMock:
    """Build a mock async httpx client that returns ``resp`` for any GET."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ---------------------------------------------------------------------------
# LamplightClient.get_profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_profile_returns_profile_on_200():
    resp = _mock_response(200, _PROFILE_RESPONSE)
    mock_client = _mock_httpx_client(resp)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="test-key",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )
    profile = await client.get_profile("person-42")

    assert profile is not None
    assert profile.profile_id == "person-42"
    assert profile.name == "Alex Sample"
    assert profile.tags == ["befriending", "mental-health"]


@pytest.mark.asyncio
async def test_get_profile_returns_none_on_404():
    resp = _mock_response(404)
    mock_client = _mock_httpx_client(resp)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="test-key",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )
    profile = await client.get_profile("missing-person")

    assert profile is None


# ---------------------------------------------------------------------------
# LamplightClient.get_outcomes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_outcomes_returns_outcomes_list():
    resp = _mock_response(200, _OUTCOMES_RESPONSE)
    mock_client = _mock_httpx_client(resp)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="test-key",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )
    outcomes = await client.get_outcomes("person-42")

    assert len(outcomes) == 4
    assert outcomes[0].outcome_id == "out-1"
    assert outcomes[0].measurement_type == "WEMWBS"
    assert outcomes[0].value == 40
    assert outcomes[2].measurement_type == "OUTCOME_STAR"
    assert outcomes[2].value == 3


# ---------------------------------------------------------------------------
# LamplightClient.get_work_records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_work_records_returns_work_records_list():
    resp = _mock_response(200, _WORK_RECORDS_RESPONSE)
    mock_client = _mock_httpx_client(resp)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="test-key",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )
    records = await client.get_work_records("person-42")

    assert len(records) == 2
    assert records[0].record_id == "work-1"
    assert records[0].type == "1-2-1 session"
    assert records[0].project == "Befriending"
    assert records[1].record_id == "work-2"


# ---------------------------------------------------------------------------
# Network error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_handles_network_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="test-key",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )

    # All read methods should swallow network errors and return safe defaults.
    assert await client.get_profile("person-42") is None
    assert await client.get_outcomes("person-42") == []
    assert await client.get_work_records("person-42") == []


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_uses_correct_auth_header():
    resp = _mock_response(200, _PROFILE_RESPONSE)
    mock_client = _mock_httpx_client(resp)

    factory = MagicMock(return_value=mock_client)
    client = LamplightClient(
        api_key="secret-key-123",
        base_url="https://example.lamplight.online/api",
        http_client_factory=factory,
    )
    await client.get_profile("person-42")

    # httpx client.get(url, headers=...) — headers passed as kwarg.
    headers = mock_client.get.call_args.kwargs.get("headers", {})
    assert headers.get("X-Lamplight-Key") == "secret-key-123"


# ---------------------------------------------------------------------------
# outcomes_to_evidence
# ---------------------------------------------------------------------------


def test_outcomes_to_evidence_groups_by_measurement_type():
    outcomes = [
        LamplightOutcome("out-1", "p1", "WEMWBS", 40, "2024-01-01", None),
        LamplightOutcome("out-2", "p1", "WEMWBS", 56, "2024-06-01", None),
        LamplightOutcome("out-3", "p1", "OUTCOME_STAR", 3, "2024-01-05", None),
        LamplightOutcome("out-4", "p1", "OUTCOME_STAR", 7, "2024-06-05", None),
    ]
    items = outcomes_to_evidence(outcomes)
    # One evidence item per measurement_type group.
    types = {item["outcomes"][0]["metric"] for item in items}
    assert types == {"WEMWBS", "OUTCOME_STAR"}
    assert len(items) == 2


def test_outcomes_to_evidence_calculates_baseline_to_followup_change():
    outcomes = [
        LamplightOutcome("out-1", "p1", "WEMWBS", 40, "2024-01-01", None),
        LamplightOutcome("out-2", "p1", "WEMWBS", 56, "2024-06-01", None),
    ]
    items = outcomes_to_evidence(outcomes)
    assert len(items) == 1
    outcome = items[0]["outcomes"][0]
    assert outcome["metric"] == "WEMWBS"
    assert outcome["baseline"] == 40
    assert outcome["follow_up"] == 56
    assert outcome["change"] == 16
    assert outcome["n"] == 2


def test_outcomes_to_evidence_handles_single_measurement():
    outcomes = [
        LamplightOutcome("out-1", "p1", "WEMWBS", 45, "2024-01-01", None),
    ]
    items = outcomes_to_evidence(outcomes)
    assert len(items) == 1
    outcome = items[0]["outcomes"][0]
    assert outcome["baseline"] == 45
    assert outcome["follow_up"] == 45
    assert outcome["change"] == 0
    assert outcome["n"] == 1


def test_outcomes_to_evidence_empty_list():
    assert outcomes_to_evidence([]) == []


def test_outcomes_to_evidence_generates_unique_evidence_ids():
    outcomes = [
        LamplightOutcome("out-1", "p1", "WEMWBS", 40, "2024-01-01", None),
        LamplightOutcome("out-2", "p1", "WEMWBS", 56, "2024-06-01", None),
        LamplightOutcome("out-3", "p1", "OUTCOME_STAR", 3, "2024-01-05", None),
        LamplightOutcome("out-4", "p1", "OUTCOME_STAR", 7, "2024-06-05", None),
        LamplightOutcome("out-5", "p1", "PHQ6", 12, "2024-02-01", None),
    ]
    items = outcomes_to_evidence(outcomes)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)
    # Each id should reference the lamplight source and the metric.
    for item in items:
        assert "lamplight" in item["evidence_id"]


# ---------------------------------------------------------------------------
# work_records_to_evidence
# ---------------------------------------------------------------------------


def test_work_records_to_evidence_maps_records_to_case_study_items():
    records = [
        LamplightWorkRecord("work-1", "p1", "1-2-1 session", "2024-04-01", "Befriending", "Initial session"),
        LamplightWorkRecord("work-2", "p1", "Group activity", "2024-04-15", "Befriending", None),
    ]
    items = work_records_to_evidence(records)
    assert len(items) == 2
    for item in items:
        assert item["evidence_type"] == "case_study"
    assert items[0]["date"] == "2024-04-01"
    assert "Befriending" in items[0]["title"]
    assert items[1]["record_id"] == "work-2" or items[1]["evidence_id"].endswith("work-2") or "work-2" in items[1]["evidence_id"]


def test_work_records_to_evidence_empty_list():
    assert work_records_to_evidence([]) == []


def test_work_records_to_evidence_generates_unique_evidence_ids():
    records = [
        LamplightWorkRecord("work-1", "p1", "session", "2024-04-01", "P", None),
        LamplightWorkRecord("work-2", "p1", "session", "2024-04-02", "P", None),
        LamplightWorkRecord("work-3", "p1", "session", "2024-04-03", "P", None),
    ]
    items = work_records_to_evidence(records)
    ids = [i["evidence_id"] for i in items]
    assert len(set(ids)) == len(ids)