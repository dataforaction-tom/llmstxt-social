"""Tests for the dev-mode magic-link logger.

When ``settings.environment == "development"``, the auth route and Open Org
claim email both print the magic link to stdout instead of sending via Resend.
Lets a developer click through the full flow locally without configuring
Resend deliverability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


# --- /auth/magic-link route ------------------------------------------------


@pytest.mark.asyncio
async def test_send_magic_link_in_dev_logs_link_and_skips_resend(capsys):
    from llmstxt_api.routes.auth import send_magic_link
    from llmstxt_api.schemas import MagicLinkRequest

    session = mock.AsyncMock()
    request = MagicLinkRequest(email="owner@example.com")

    with mock.patch(
        "llmstxt_api.routes.auth.settings.environment", "development"
    ), mock.patch(
        "llmstxt_api.routes.auth.resend.Emails.send"
    ) as send_mock:
        await send_magic_link(request, session)

    send_mock.assert_not_called()
    captured = capsys.readouterr()
    assert "owner@example.com" in captured.out
    # The URL must be present so the developer can copy-paste.
    assert "/auth/verify?token=" in captured.out


@pytest.mark.asyncio
async def test_send_magic_link_in_production_still_calls_resend():
    from llmstxt_api.routes.auth import send_magic_link
    from llmstxt_api.schemas import MagicLinkRequest

    session = mock.AsyncMock()
    request = MagicLinkRequest(email="owner@example.com")

    with mock.patch(
        "llmstxt_api.routes.auth.settings.environment", "production"
    ), mock.patch(
        "llmstxt_api.routes.auth.resend.Emails.send"
    ) as send_mock:
        await send_magic_link(request, session)

    send_mock.assert_called_once()


# --- Open Org claim email --------------------------------------------------


@pytest.mark.asyncio
async def test_claim_email_in_dev_prints_link_and_skips_resend(capsys):
    """The Open Org generator's claim email path mirrors the login path."""
    from llmstxt_api.tasks.open_org_generate import _default_send_claim_email

    session = mock.AsyncMock()

    with mock.patch(
        "llmstxt_api.tasks.open_org_generate.settings.environment", "development"
    ), mock.patch(
        "llmstxt_api.tasks.open_org_generate.resend.Emails.send"
    ) as send_mock:
        await _default_send_claim_email(
            db=session, email="owner@example.com", org_id="GB-CHC-1234567"
        )

    send_mock.assert_not_called()
    captured = capsys.readouterr()
    assert "owner@example.com" in captured.out
    assert "GB-CHC-1234567" in captured.out
    assert "/auth/verify?token=" in captured.out


@pytest.mark.asyncio
async def test_claim_email_in_production_still_calls_resend():
    from llmstxt_api.tasks.open_org_generate import _default_send_claim_email

    session = mock.AsyncMock()

    with mock.patch(
        "llmstxt_api.tasks.open_org_generate.settings.environment", "production"
    ), mock.patch(
        "llmstxt_api.tasks.open_org_generate.resend.Emails.send"
    ) as send_mock:
        await _default_send_claim_email(
            db=session, email="owner@example.com", org_id="GB-CHC-1234567"
        )

    send_mock.assert_called_once()
