"""Tests for the PAYMENTS_ENABLED kill switch.

When off (the default), the full pipeline (enrichment + assessment) is free:
/api/generate/free queues the full-pipeline task, and the one-time payment
endpoints refuse with 403. The Stripe webhook and subscriptions routes are
deliberately untouched — monitoring stays paid.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


# --- Settings ---------------------------------------------------------------


def test_payments_disabled_by_default():
    from llmstxt_api.config import Settings

    assert Settings().payments_enabled is False


def test_payments_enabled_via_env(monkeypatch):
    from llmstxt_api.config import Settings

    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    assert Settings().payments_enabled is True


# --- Helpers ----------------------------------------------------------------


def make_db():
    """AsyncMock db whose refresh() stamps created_at so JobResponse validates."""
    db = mock.AsyncMock()

    async def fake_refresh(obj):
        obj.created_at = datetime.utcnow()

    db.refresh = mock.AsyncMock(side_effect=fake_refresh)
    return db


def make_http_request():
    http_request = mock.MagicMock()
    http_request.client.host = "203.0.113.7"
    return http_request


# --- /api/generate/free -----------------------------------------------------


@pytest.mark.asyncio
async def test_free_endpoint_runs_full_pipeline_when_payments_disabled():
    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_free
    from llmstxt_api.schemas import GenerateRequest

    db = make_db()
    request = GenerateRequest(url="https://example.org", template="charity")

    free_task = mock.MagicMock()
    paid_task = mock.MagicMock()
    with mock.patch.object(settings, "payments_enabled", False), mock.patch(
        "llmstxt_api.routes.generate.generate_free_task", free_task
    ), mock.patch("llmstxt_api.routes.generate.generate_paid_task", paid_task):
        response = await generate_free(request, make_http_request(), db)

    # Full pipeline queued; the basic free task is bypassed.
    paid_task.delay.assert_called_once()
    free_task.delay.assert_not_called()

    # Free-tier limits unchanged: tier stays "free", expiry stays ~7 days.
    job = db.add.call_args.args[0]
    assert job.tier == "free"
    assert job.expires_at < datetime.utcnow() + timedelta(days=8)
    assert response.tier == "free"


@pytest.mark.asyncio
async def test_free_endpoint_keeps_basic_pipeline_when_payments_enabled():
    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_free
    from llmstxt_api.schemas import GenerateRequest

    db = make_db()
    request = GenerateRequest(url="https://example.org", template="charity")

    free_task = mock.MagicMock()
    paid_task = mock.MagicMock()
    with mock.patch.object(settings, "payments_enabled", True), mock.patch(
        "llmstxt_api.routes.generate.generate_free_task", free_task
    ), mock.patch("llmstxt_api.routes.generate.generate_paid_task", paid_task):
        await generate_free(request, make_http_request(), db)

    free_task.delay.assert_called_once()
    paid_task.delay.assert_not_called()
