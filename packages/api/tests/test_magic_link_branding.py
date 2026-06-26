"""Magic-link emails are Open Org-branded when the base URL is the Open Org
host, llms.txt-branded otherwise."""
from __future__ import annotations
from unittest import mock


def test_openorg_base_uses_openorg_branding():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "openorg_from_email", "Open Org <hello@openorg.good-ship.co.uk>"
    ):
        b = auth._email_branding("https://openorg.good-ship.co.uk")
    assert b["from_email"] == "Open Org <hello@openorg.good-ship.co.uk>"
    assert "Open Org" in b["subject"]
    assert "llms.txt" not in b["subject"]


def test_llmstxt_base_uses_default_branding():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "from_email", "llmstxt <x@resend.dev>"):
        b = auth._email_branding("https://llmstxt.social")
    assert b["from_email"] == "llmstxt <x@resend.dev>"
    assert "llms.txt" in b["subject"].lower()
