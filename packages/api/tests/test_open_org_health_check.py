"""Tests for the weekly Murmurations health-check task.

Re-validates every published profile's federated envelope against the live
Murmurations schema and flags drift. Recovery (drift → validated) happens
automatically on the next run.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


def _profile(*, org_id: str, status: str = "validated", published: bool = True):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        published=published,
        murmurations_status=status,
        murmurations_node_id="node-123" if status == "validated" else None,
        profile_json={"identity": {"name": org_id}},
    )


def _session_maker_with(profiles):
    """Return a session_maker callable whose context manager yields a session
    that returns ``profiles`` from select(OrgProfile).execute()."""
    session = mock.AsyncMock()
    select_result = mock.MagicMock()
    select_result.scalars.return_value.all.return_value = profiles
    session.execute.return_value = select_result

    class _CM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return None

    return lambda: _CM(), session


async def test_health_check_marks_drift_when_validation_fails():
    from llmstxt_api.tasks.open_org_murmurations import _run_health_check

    profile = _profile(org_id="GB-CHC-1")
    maker, session = _session_maker_with([profile])

    client = mock.AsyncMock()
    client.validate_profile.return_value = {"valid": False, "errors": ["e"]}

    counts = await _run_health_check(
        session_maker=maker,
        client=client,
        frontend_base_url="https://openorg.example",
    )

    assert profile.murmurations_status == "drift"
    assert counts == {"checked": 1, "drifted": 1, "errored": 0}
    client.validate_profile.assert_called_once_with(
        "https://openorg.example/open-org/GB-CHC-1/murmurations.json"
    )
    session.commit.assert_called()


async def test_health_check_leaves_validated_state_when_valid():
    from llmstxt_api.tasks.open_org_murmurations import _run_health_check

    profile = _profile(org_id="GB-CHC-1")
    maker, session = _session_maker_with([profile])

    client = mock.AsyncMock()
    client.validate_profile.return_value = {"valid": True}

    counts = await _run_health_check(
        session_maker=maker,
        client=client,
        frontend_base_url="https://openorg.example",
    )

    assert profile.murmurations_status == "validated"
    assert counts == {"checked": 1, "drifted": 0, "errored": 0}


async def test_health_check_recovers_from_drift_when_validation_succeeds():
    from llmstxt_api.tasks.open_org_murmurations import _run_health_check

    profile = _profile(org_id="GB-CHC-1", status="drift")
    maker, _ = _session_maker_with([profile])

    client = mock.AsyncMock()
    client.validate_profile.return_value = {"valid": True}

    await _run_health_check(
        session_maker=maker,
        client=client,
        frontend_base_url="https://openorg.example",
    )

    assert profile.murmurations_status == "validated"


async def test_health_check_skips_unpublished_profiles():
    """The SELECT already filters to published=True, so unpublished rows
    never show up in the loop. Sanity-check with a profile the helper would
    not return."""
    from llmstxt_api.tasks.open_org_murmurations import _run_health_check

    # No published profiles
    maker, _ = _session_maker_with([])

    client = mock.AsyncMock()

    counts = await _run_health_check(
        session_maker=maker,
        client=client,
        frontend_base_url="https://openorg.example",
    )

    assert counts == {"checked": 0, "drifted": 0, "errored": 0}
    client.validate_profile.assert_not_called()


async def test_health_check_counts_transient_errors_without_flagging():
    """A 5xx during validation shouldn't be flagged as drift — that's a
    network issue, not a schema mismatch."""
    from llmstxt_api.tasks.open_org_murmurations import _run_health_check
    from llmstxt_core.open_org.murmurations import MurmurationsError

    profile = _profile(org_id="GB-CHC-1")
    maker, _ = _session_maker_with([profile])

    client = mock.AsyncMock()
    client.validate_profile.side_effect = MurmurationsError("503 from index")

    counts = await _run_health_check(
        session_maker=maker,
        client=client,
        frontend_base_url="https://openorg.example",
    )

    assert profile.murmurations_status == "validated"  # unchanged
    assert counts == {"checked": 1, "drifted": 0, "errored": 1}
