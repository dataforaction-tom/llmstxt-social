"""Tests for the POST /api/open-org/generate route.

The route is intentionally unauthenticated — the spec wants anyone to be able
to kick off a profile generation by charity number. Ownership is established
later by the claim link emailed to ``owner_email``.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


# --- Validation -------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_non_numeric_charity_number():
    from llmstxt_api.routes.open_org_generate import (
        GenerateRequest,
        generate_profile,
    )

    db = mock.AsyncMock()

    with pytest.raises(Exception) as exc:
        # Pydantic-level validation: bad charity number format must error.
        GenerateRequest(charity_number="ABC123", owner_email="o@example.com")
    assert "charity" in str(exc.value).lower() or "string" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_rejects_invalid_email():
    from llmstxt_api.routes.open_org_generate import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest(charity_number="1234567", owner_email="not-an-email")


# --- Happy path ------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_creates_profile_row_and_dispatches_task():
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import (
        GenerateRequest,
        generate_profile,
    )

    db = mock.AsyncMock()
    no_existing = mock.MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    db.execute.return_value = no_existing

    request = GenerateRequest(
        charity_number="1234567", owner_email="owner@example.com"
    )

    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="celery-task-id-abc")

    with mock.patch(
        "llmstxt_api.routes.open_org_generate.generate_open_org_profile_task",
        task_mock,
    ):
        response = await generate_profile(request, db)

    # An OrgProfile row was created with the right org_id and status.
    added = db.add.call_args.args[0]
    assert isinstance(added, OrgProfile)
    assert added.org_id == "GB-CHC-1234567"
    assert added.generation_status == "pending"

    # Celery task was dispatched with the new row id + owner email.
    task_mock.delay.assert_called_once()
    kwargs = task_mock.delay.call_args.kwargs
    assert kwargs["owner_email"] == "owner@example.com"
    assert "profile_id" in kwargs

    assert response.org_id == "GB-CHC-1234567"
    assert response.generation_status == "pending"


# --- Conflict -------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_409_when_org_already_exists():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import (
        GenerateRequest,
        generate_profile,
    )

    existing = OrgProfile(
        id=uuid.uuid4(), org_id="GB-CHC-1234567", generation_status="ready"
    )
    db = mock.AsyncMock()
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result

    request = GenerateRequest(
        charity_number="1234567", owner_email="owner@example.com"
    )

    with pytest.raises(HTTPException) as exc:
        await generate_profile(request, db)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_allows_retry_when_previous_generation_failed():
    """A previous run that hit a transient failure (status=failed) should be
    retryable without manual cleanup. The row is re-used and re-queued."""
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import (
        GenerateRequest,
        generate_profile,
    )

    existing = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        generation_status="failed",
        generation_error="CC API timeout",
    )
    db = mock.AsyncMock()
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result

    request = GenerateRequest(
        charity_number="1234567", owner_email="owner@example.com"
    )

    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="celery-id")

    with mock.patch(
        "llmstxt_api.routes.open_org_generate.generate_open_org_profile_task",
        task_mock,
    ):
        response = await generate_profile(request, db)

    # No new row added; existing one re-used.
    db.add.assert_not_called()
    assert existing.generation_status == "pending"
    assert existing.generation_error is None
    task_mock.delay.assert_called_once()
    assert response.generation_status == "pending"
