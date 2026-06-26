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
