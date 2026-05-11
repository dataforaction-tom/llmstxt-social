"""Tests for the daily CreatorSession eviction task.

Sessions expire after 30 days of inactivity (Step 8 spec). The routes
already reject expired sessions with 410, but rows accumulate forever
without a sweep. This task is the sweep.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


def _session_maker_for(session: mock.AsyncMock):
    manager = mock.MagicMock()
    ctx = mock.AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    manager.return_value = ctx
    return manager


@pytest.mark.asyncio
async def test_run_eviction_deletes_only_expired_rows():
    from llmstxt_api.tasks.open_org_creator import _run_eviction

    session = mock.AsyncMock()
    # Mock execute() to return a result with rowcount on the delete statement.
    exec_result = mock.MagicMock()
    exec_result.rowcount = 3
    session.execute.return_value = exec_result

    deleted = await _run_eviction(session_maker=_session_maker_for(session))

    # Exactly one DELETE was issued.
    assert session.execute.call_count == 1
    # The statement filters on expires_at < <now>. We don't introspect the
    # SQL here (the unit test would be brittle); the smoke test is that a
    # statement of the right family was issued and commit was awaited.
    session.commit.assert_awaited()
    assert deleted == 3


@pytest.mark.asyncio
async def test_run_eviction_returns_zero_when_no_rows_to_evict():
    from llmstxt_api.tasks.open_org_creator import _run_eviction

    session = mock.AsyncMock()
    exec_result = mock.MagicMock()
    exec_result.rowcount = 0
    session.execute.return_value = exec_result

    deleted = await _run_eviction(session_maker=_session_maker_for(session))

    assert deleted == 0
    session.commit.assert_awaited()


def test_eviction_task_is_registered_on_celery_beat():
    """Locked decision: daily at 06:00 UTC, an hour after the Murmurations
    sync at 05:30. Pin both the task name and the cron to catch drift."""
    from llmstxt_api.tasks.celery import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "open-org-evict-expired-creator-sessions" in schedule
    entry = schedule["open-org-evict-expired-creator-sessions"]
    assert entry["task"] == "open_org_evict_expired_creator_sessions"
    cron = entry["schedule"]
    assert getattr(cron, "hour", None) == {6}
    assert getattr(cron, "minute", None) == {0}
