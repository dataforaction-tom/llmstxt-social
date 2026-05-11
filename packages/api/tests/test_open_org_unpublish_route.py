"""Tests for POST /api/open-org/{org_id}/unpublish + the node-delete task.

Unpublishing flips ``OrgProfile.published`` to False, hiding the public
JSON, and dispatches a Celery task that removes the Murmurations index
node so federated discovery doesn't keep showing a stale entry.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


def _admin_for(org_id: str = "GB-CHC-1234567"):
    from llmstxt_api.open_org_models import OrgAdmin

    return OrgAdmin(user_id=uuid.uuid4(), org_id=org_id, role="owner")


def _profile(
    *,
    published: bool = True,
    node_id: str | None = "node-abc",
    status_str: str = "posted",
):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        published=published,
        murmurations_node_id=node_id,
        murmurations_status=status_str,
        profile_json={"schema_version": "open-org/v0.1"},
    )


# --- route -----------------------------------------------------------------


async def test_unpublish_sets_published_false_and_queues_node_delete():
    from llmstxt_api.routes.open_org_admin import unpublish_profile

    profile = _profile()
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    admin = _admin_for()

    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="task-del")

    with mock.patch(
        "llmstxt_api.routes.open_org_admin.delete_from_murmurations_task",
        task_mock,
    ):
        response = await unpublish_profile("GB-CHC-1234567", db, admin)

    assert profile.published is False
    task_mock.delay.assert_called_once()
    kwargs = task_mock.delay.call_args.kwargs
    assert kwargs["profile_id"] == str(profile.id)
    assert response.org_id == "GB-CHC-1234567"
    assert response.published is False


async def test_unpublish_skips_delete_task_when_no_node_on_file():
    """Profile was never submitted to the index, so there's nothing to
    delete — flip published=False and return; don't dispatch."""
    from llmstxt_api.routes.open_org_admin import unpublish_profile

    profile = _profile(node_id=None, status_str="pending")
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    admin = _admin_for()

    task_mock = mock.MagicMock()
    with mock.patch(
        "llmstxt_api.routes.open_org_admin.delete_from_murmurations_task",
        task_mock,
    ):
        await unpublish_profile("GB-CHC-1234567", db, admin)

    assert profile.published is False
    task_mock.delay.assert_not_called()


async def test_unpublish_returns_404_when_profile_missing():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_admin import unpublish_profile

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=None)
    )
    admin = _admin_for(org_id="GB-CHC-NONE")

    with pytest.raises(HTTPException) as exc:
        await unpublish_profile("GB-CHC-NONE", db, admin)
    assert exc.value.status_code == 404


# --- task ------------------------------------------------------------------


def _session_maker_for(session):
    manager = mock.MagicMock()
    ctx = mock.AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    manager.return_value = ctx
    return manager


async def test_run_node_delete_calls_client_and_clears_state():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    profile = _profile(node_id="node-abc", status_str="posted")
    session = mock.AsyncMock()
    session.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )

    client = mock.AsyncMock()
    client.delete_node = mock.AsyncMock()

    await task_mod._run_node_delete(
        profile_id=profile.id,
        session_maker=_session_maker_for(session),
        client=client,
    )

    client.delete_node.assert_awaited_once_with("node-abc")
    assert profile.murmurations_node_id is None
    assert profile.murmurations_status == "deleted"


async def test_run_node_delete_is_noop_when_no_node_id():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    profile = _profile(node_id=None, status_str="pending")
    session = mock.AsyncMock()
    session.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    client = mock.AsyncMock()

    await task_mod._run_node_delete(
        profile_id=profile.id,
        session_maker=_session_maker_for(session),
        client=client,
    )

    client.delete_node.assert_not_awaited()
    assert profile.murmurations_status == "pending"  # unchanged


async def test_run_node_delete_propagates_5xx_for_retry():
    from llmstxt_core.open_org.murmurations import MurmurationsError
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    profile = _profile()
    session = mock.AsyncMock()
    session.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    client = mock.AsyncMock()
    client.delete_node = mock.AsyncMock(side_effect=MurmurationsError("503"))

    with pytest.raises(MurmurationsError):
        await task_mod._run_node_delete(
            profile_id=profile.id,
            session_maker=_session_maker_for(session),
            client=client,
        )
    # State unchanged so the retry can try again cleanly.
    assert profile.murmurations_node_id == "node-abc"
    assert profile.murmurations_status == "posted"
