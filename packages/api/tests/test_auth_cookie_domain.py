"""Tests for the env-driven ``auth_cookie_domain`` setting.

Setting ``AUTH_COOKIE_DOMAIN=.good-ship.co.uk`` makes the auth cookie span
subdomains (Step 10 / locked decision #9). When unset, the cookie is host-only
(current behaviour) so dev on localhost still works.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


def _magic_token(*, email: str = "owner@example.com"):
    from llmstxt_api.models import MagicLinkToken

    return MagicLinkToken(
        id=uuid.uuid4(),
        email=email,
        token="raw-token",
        org_id=None,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )


def _user_for(email: str):
    from llmstxt_api.models import User

    return User(id=uuid.uuid4(), email=email, created_at=datetime.utcnow())


def _db_with(token, user):
    db = mock.AsyncMock()
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db.execute.side_effect = [token_result, user_result]
    return db


async def test_set_cookie_uses_configured_domain():
    """When AUTH_COOKIE_DOMAIN is set, the auth cookie carries Domain=."""
    from fastapi import Response

    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    token = _magic_token()
    user = _user_for(token.email)
    db = _db_with(token, user)
    response = Response()

    with mock.patch(
        "llmstxt_api.routes.auth.settings.auth_cookie_domain",
        ".good-ship.co.uk",
    ):
        await verify_magic_link(
            VerifyTokenRequest(token="raw-token"), response, db
        )

    cookie_header = response.headers.get("set-cookie", "")
    assert "Domain=.good-ship.co.uk" in cookie_header
    assert "auth_token=" in cookie_header


async def test_set_cookie_omits_domain_when_unset():
    """No AUTH_COOKIE_DOMAIN → host-only cookie (dev mode)."""
    from fastapi import Response

    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    token = _magic_token()
    user = _user_for(token.email)
    db = _db_with(token, user)
    response = Response()

    with mock.patch(
        "llmstxt_api.routes.auth.settings.auth_cookie_domain", None
    ):
        await verify_magic_link(
            VerifyTokenRequest(token="raw-token"), response, db
        )

    cookie_header = response.headers.get("set-cookie", "")
    assert "auth_token=" in cookie_header
    assert "Domain=" not in cookie_header


async def test_logout_uses_configured_domain():
    """delete_cookie must match the set Domain or the browser keeps the cookie."""
    from fastapi import Response

    from llmstxt_api.routes.auth import logout

    response = Response()
    with mock.patch(
        "llmstxt_api.routes.auth.settings.auth_cookie_domain",
        ".good-ship.co.uk",
    ):
        await logout(response)

    cookie_header = response.headers.get("set-cookie", "")
    # Browser delete = a Set-Cookie with Max-Age=0 (or expired). Domain must
    # match the one used when setting, otherwise the browser ignores it.
    assert "Domain=.good-ship.co.uk" in cookie_header


def test_settings_default_auth_cookie_domain_is_none():
    """Default keeps current behaviour so dev (localhost) keeps working."""
    from llmstxt_api.config import Settings

    # Construct fresh to avoid the imported module-level instance.
    fresh = Settings(
        database_url="postgresql://t",
        redis_url="redis://t",
        anthropic_api_key="t",
        stripe_secret_key="t",
        stripe_webhook_secret="t",
        resend_api_key="t",
        secret_key="t",
    )
    assert fresh.auth_cookie_domain is None
