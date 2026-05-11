"""Tests for collect_website_text — Phase 1.5 (v0.2.1).

Feeds the theme extractor with content from the charity's own website. The
v0.1 baseline showed CC ``who_what_where`` text alone misses obvious themes
(Trussell missing food_access; Shelter missing housing_and_homelessness).
"""

from __future__ import annotations

from unittest import mock

import pytest

from llmstxt_core.crawler import CrawlResult, Page
from llmstxt_core.extractor import ExtractedPage, PageType
from llmstxt_core.open_org.website_text import collect_website_text


def _page(url: str, html: str = "<html></html>") -> Page:
    return Page(url=url, html=html, title="", status_code=200)


def _extracted(*, url: str, body: str, page_type: PageType) -> ExtractedPage:
    return ExtractedPage(
        url=url,
        title="t",
        description=None,
        headings=[],
        body_text=body,
        page_type=page_type,
    )


# --- Empty / missing URL ----------------------------------------------------


async def test_returns_empty_string_for_missing_url():
    out = await collect_website_text(None)  # type: ignore[arg-type]
    assert out == ""


async def test_returns_empty_string_for_whitespace_url():
    assert await collect_website_text("   ") == ""


# --- Crawl + extract concatenation ------------------------------------------


async def test_concatenates_body_text_from_relevant_pages():
    home = _extracted(
        url="https://acme.example/", body="Acme runs food banks.", page_type=PageType.HOME
    )
    about = _extracted(
        url="https://acme.example/about",
        body="We help people in crisis.",
        page_type=PageType.ABOUT,
    )

    async def fake_crawl(url, max_pages):
        return CrawlResult(
            pages=[_page("https://acme.example/"), _page("https://acme.example/about")],
            base_url=url,
        )

    def fake_extract(page):
        return home if page.url.endswith("/") else about

    text = await collect_website_text(
        "https://acme.example",
        crawler=fake_crawl,
        extractor=fake_extract,
        max_pages=5,
    )
    assert "Acme runs food banks." in text
    assert "We help people in crisis." in text


async def test_skips_pages_with_low_signal_page_types():
    """Donate/contact/team pages are mostly boilerplate — don't dilute the prompt."""
    home = _extracted(url="https://x.example/", body="HOME BODY", page_type=PageType.HOME)
    donate = _extracted(
        url="https://x.example/donate", body="DONATE BODY", page_type=PageType.DONATE
    )

    async def fake_crawl(url, max_pages):
        return CrawlResult(
            pages=[_page("https://x.example/"), _page("https://x.example/donate")],
            base_url=url,
        )

    def fake_extract(page):
        return home if "donate" not in page.url else donate

    text = await collect_website_text(
        "https://x.example",
        crawler=fake_crawl,
        extractor=fake_extract,
        max_pages=5,
    )
    assert "HOME BODY" in text
    assert "DONATE BODY" not in text


async def test_respects_max_pages_cap_passed_to_crawler():
    """Phase 1.5 caps crawl spend per generation. Cap must reach the crawler."""
    captured: dict = {}

    async def fake_crawl(url, max_pages):
        captured["max_pages"] = max_pages
        return CrawlResult(pages=[], base_url=url, errors=[], sitemap_used=False)

    await collect_website_text(
        "https://x.example", crawler=fake_crawl, extractor=lambda p: None, max_pages=3
    )
    assert captured["max_pages"] == 3


async def test_truncates_to_max_chars():
    """A pathologically long site shouldn't blow the prompt budget."""
    big_body = "z" * 100_000
    home = _extracted(url="https://x.example/", body=big_body, page_type=PageType.HOME)

    async def fake_crawl(url, max_pages):
        return CrawlResult(
            pages=[_page("https://x.example/")],
            base_url=url,
        )

    text = await collect_website_text(
        "https://x.example",
        crawler=fake_crawl,
        extractor=lambda p: home,
        max_pages=5,
        max_chars=5_000,
    )
    assert len(text) <= 5_000


# --- Failure paths ---------------------------------------------------------


async def test_returns_empty_string_when_crawler_raises():
    """A bad website (timeout, DNS failure, 403) must not break generation."""

    async def fake_crawl(url, max_pages):
        raise RuntimeError("DNS lookup failed")

    text = await collect_website_text(
        "https://broken.example",
        crawler=fake_crawl,
        extractor=lambda p: None,
        max_pages=5,
    )
    assert text == ""


async def test_returns_empty_string_when_extractor_returns_empty_bodies():
    home = _extracted(url="https://x.example/", body="", page_type=PageType.HOME)

    async def fake_crawl(url, max_pages):
        return CrawlResult(
            pages=[_page("https://x.example/")],
            base_url=url,
        )

    text = await collect_website_text(
        "https://x.example",
        crawler=fake_crawl,
        extractor=lambda p: home,
        max_pages=5,
    )
    assert text == ""


async def test_returns_empty_string_when_crawler_returns_no_pages():
    async def fake_crawl(url, max_pages):
        return CrawlResult(pages=[], base_url=url, errors=[], sitemap_used=False)

    text = await collect_website_text(
        "https://x.example",
        crawler=fake_crawl,
        extractor=lambda p: None,
        max_pages=5,
    )
    assert text == ""


async def test_skips_individual_extract_failures_but_keeps_rest():
    home = _extracted(url="https://x.example/", body="GOOD HOME", page_type=PageType.HOME)

    async def fake_crawl(url, max_pages):
        return CrawlResult(
            pages=[_page("https://x.example/"), _page("https://x.example/about")],
            base_url=url,
        )

    def flaky_extract(page):
        if "about" in page.url:
            raise ValueError("malformed HTML")
        return home

    text = await collect_website_text(
        "https://x.example",
        crawler=fake_crawl,
        extractor=flaky_extract,
        max_pages=5,
    )
    assert "GOOD HOME" in text
