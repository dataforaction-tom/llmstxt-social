"""The magic-link base URL must come from the request's validated Origin,
never an unvalidated/spoofed host. Falls back to settings.frontend_url."""
from __future__ import annotations

from unittest import mock
import pytest


def _req(origin: str | None):
    headers = {"origin": origin} if origin else {}
    return mock.Mock(headers=headers)


def test_allowed_openorg_origin_is_used():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist",
        "https://llmstxt.social,https://openorg.good-ship.co.uk",
    ), mock.patch.object(auth.settings, "environment", "production"):
        base = auth._resolve_frontend_base(_req("https://openorg.good-ship.co.uk"))
    assert base == "https://openorg.good-ship.co.uk"


def test_allowed_llmstxt_origin_is_used():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist",
        "https://llmstxt.social,https://openorg.good-ship.co.uk",
    ), mock.patch.object(auth.settings, "environment", "production"):
        base = auth._resolve_frontend_base(_req("https://llmstxt.social"))
    assert base == "https://llmstxt.social"


def test_spoofed_origin_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist", "https://llmstxt.social",
    ), mock.patch.object(auth.settings, "environment", "production"), \
         mock.patch.object(auth.settings, "frontend_url", "https://llmstxt.social"):
        base = auth._resolve_frontend_base(_req("https://evil.example.com"))
    assert base == "https://llmstxt.social"
    assert "evil.example.com" not in base


def test_missing_origin_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "frontend_url", "http://localhost:3000"):
        base = auth._resolve_frontend_base(_req(None))
    assert base == "http://localhost:3000"


def test_none_request_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "frontend_url", "http://localhost:3000"):
        assert auth._resolve_frontend_base(None) == "http://localhost:3000"


def test_subdomain_lookalike_origin_does_not_bypass_allowlist():
    """A look-alike host that merely *contains* an allowlisted host as a prefix
    must NOT match — the allowlist is exact-string, not substring/startswith."""
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist", "https://llmstxt.social",
    ), mock.patch.object(auth.settings, "environment", "production"), \
         mock.patch.object(auth.settings, "frontend_url", "https://llmstxt.social"):
        base = auth._resolve_frontend_base(_req("https://llmstxt.social.evil.com"))
    assert base == "https://llmstxt.social"
    assert "evil.com" not in base


def test_dev_localhost_origin_is_allowed():
    """In development the localhost dev origins are allowlisted."""
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist", "https://llmstxt.social",
    ), mock.patch.object(auth.settings, "environment", "development"):
        base = auth._resolve_frontend_base(_req("http://localhost:5173"))
    assert base == "http://localhost:5173"


@pytest.mark.asyncio
async def test_endpoint_threads_openorg_origin_into_link_and_branding():
    """End-to-end wiring: the endpoint must build the emailed link from the
    request Origin and apply the matching brand to the Resend payload."""
    from llmstxt_api.routes import auth
    from llmstxt_api.schemas import MagicLinkRequest

    session = mock.AsyncMock()
    session.add = mock.Mock()  # add() is synchronous; avoid a never-awaited warning
    req = MagicLinkRequest(email="funder@example.com")

    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist",
        "https://llmstxt.social,https://openorg.good-ship.co.uk",
    ), mock.patch.object(auth.settings, "environment", "production"), \
         mock.patch.object(
             auth.settings, "openorg_from_email",
             "Open Org <hello@openorg.good-ship.co.uk>",
         ), mock.patch.object(auth.resend.Emails, "send") as send_mock:
        await auth.send_magic_link(req, session, _req("https://openorg.good-ship.co.uk"))

    send_mock.assert_called_once()
    payload = send_mock.call_args.args[0]
    assert payload["from"] == "Open Org <hello@openorg.good-ship.co.uk>"
    assert "Open Org" in payload["subject"]
    assert "https://openorg.good-ship.co.uk/auth/verify?token=" in payload["html"]
