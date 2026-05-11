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


async def test_adds_https_scheme_to_bare_hostname():
    """The CC API returns bare hostnames like 'www.example.org' — httpx
    rejects those without a scheme. Real-world finding from the v0.1 +
    v0.2.x baseline: 10/10 charities had bare-hostname URLs, all crawls
    failed silently. v0.2.1 follow-up fix."""
    captured: dict = {}

    async def fake_crawl(url, max_pages):
        captured["url"] = url
        return CrawlResult(pages=[], base_url=url)

    await collect_website_text(
        "www.oxfam.org.uk",
        crawler=fake_crawl,
        extractor=lambda p: None,
        max_pages=5,
    )
    assert captured["url"] == "https://www.oxfam.org.uk"


async def test_preserves_existing_scheme():
    captured: dict = {}

    async def fake_crawl(url, max_pages):
        captured["url"] = url
        return CrawlResult(pages=[], base_url=url)

    await collect_website_text(
        "http://x.example",
        crawler=fake_crawl,
        extractor=lambda p: None,
        max_pages=5,
    )
    # No silent upgrade to https; respect the caller's intent.
    assert captured["url"] == "http://x.example"


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


# --- v0.2.6 Playwright fallback ---------------------------------------------


async def test_playwright_fallback_fires_when_httpx_returns_no_pages():
    """Mind-class case: site returns 403 to httpx; Playwright bypasses it."""
    pw_called = {"hit": False}
    rendered_home = _extracted(
        url="https://mind.example/", body="MIND BODY", page_type=PageType.HOME
    )

    async def empty_httpx_crawl(url, max_pages):
        return CrawlResult(pages=[], base_url=url)

    async def fake_browser_fetch(url, *, max_pages):
        pw_called["hit"] = True
        return [_page("https://mind.example/")]

    text = await collect_website_text(
        "https://mind.example",
        crawler=empty_httpx_crawl,
        browser_fetch=fake_browser_fetch,
        extractor=lambda p: rendered_home,
        max_pages=5,
    )
    assert pw_called["hit"] is True
    assert "MIND BODY" in text


async def test_playwright_fallback_fires_when_httpx_raises():
    """Network errors should trigger the browser path, not silently swallow."""
    pw_called = {"hit": False}
    rendered = _extracted(
        url="https://x.example/", body="BROWSER BODY", page_type=PageType.HOME
    )

    async def boom_httpx(url, max_pages):
        raise RuntimeError("DNS lookup failed")

    async def fake_browser_fetch(url, *, max_pages):
        pw_called["hit"] = True
        return [_page("https://x.example/")]

    text = await collect_website_text(
        "https://x.example",
        crawler=boom_httpx,
        browser_fetch=fake_browser_fetch,
        extractor=lambda p: rendered,
        max_pages=5,
    )
    assert pw_called["hit"] is True
    assert "BROWSER BODY" in text


async def test_playwright_fallback_fires_when_no_relevant_pages():
    """httpx might return pages, but if every one fails the page-type
    filter (e.g. only blog/news fetched), try a browser to find real
    activity pages."""
    pw_called = {"hit": False}
    boilerplate = _extracted(
        url="https://x.example/news", body="NEWS PAGE", page_type=PageType.NEWS
    )
    real = _extracted(
        url="https://x.example/services",
        body="REAL ACTIVITIES",
        page_type=PageType.SERVICES,
    )

    async def httpx_only_news(url, max_pages):
        return CrawlResult(
            pages=[_page("https://x.example/news")], base_url=url
        )

    async def fake_browser_fetch(url, *, max_pages):
        pw_called["hit"] = True
        return [_page("https://x.example/services")]

    def fake_extract(page):
        return real if "services" in page.url else boilerplate

    text = await collect_website_text(
        "https://x.example",
        crawler=httpx_only_news,
        browser_fetch=fake_browser_fetch,
        extractor=fake_extract,
        max_pages=5,
    )
    assert pw_called["hit"] is True
    assert "REAL ACTIVITIES" in text


async def test_playwright_fallback_does_not_fire_when_httpx_succeeds():
    """Happy path: httpx returned a usable HOME page with enough content
    that the theme extractor has real signal. Don't pay the Playwright
    startup cost."""
    pw_called = {"hit": False}
    # Body length comfortably above the low-signal threshold (1500 chars).
    rendered = _extracted(
        url="https://x.example/",
        body=(
            "We are a UK charity supporting families in crisis through "
            "advocacy, education and direct services. " * 30
        ),
        page_type=PageType.HOME,
    )

    async def good_httpx(url, max_pages):
        return CrawlResult(pages=[_page("https://x.example/")], base_url=url)

    async def fake_browser_fetch(url, *, max_pages):
        pw_called["hit"] = True
        return []

    text = await collect_website_text(
        "https://x.example",
        crawler=good_httpx,
        browser_fetch=fake_browser_fetch,
        extractor=lambda p: rendered,
        max_pages=5,
    )
    assert pw_called["hit"] is False
    assert "supporting families in crisis" in text


async def test_playwright_fallback_fires_on_low_signal_single_page():
    """Shelter-class case: httpx returned the homepage and it extracted, but
    the body is too thin to give the theme extractor real activity language.
    Trigger Playwright anyway so we get the deeper pages."""
    pw_called = {"hit": False}
    thin = _extracted(
        url="https://x.example/", body="Welcome", page_type=PageType.HOME
    )
    rich = _extracted(
        url="https://x.example/services",
        body="We provide housing advice across the UK to people at risk of "
        "homelessness, plus legal support and rough sleeper outreach. " * 30,
        page_type=PageType.SERVICES,
    )

    async def thin_httpx(url, max_pages):
        return CrawlResult(pages=[_page("https://x.example/")], base_url=url)

    async def fake_browser_fetch(url, *, max_pages):
        pw_called["hit"] = True
        return [_page("https://x.example/services")]

    def fake_extract(page):
        return rich if "services" in page.url else thin

    text = await collect_website_text(
        "https://x.example",
        crawler=thin_httpx,
        browser_fetch=fake_browser_fetch,
        extractor=fake_extract,
        max_pages=5,
    )
    assert pw_called["hit"] is True
    assert "housing advice" in text


async def test_keeps_httpx_body_when_browser_returns_less():
    """Mind-class case: httpx gave us *something*; if Playwright also fails
    (still 403, or just slim pickings), don't throw away the httpx body."""
    thin = _extracted(
        url="https://x.example/", body="Welcome to our small charity.", page_type=PageType.HOME
    )

    async def thin_httpx(url, max_pages):
        return CrawlResult(pages=[_page("https://x.example/")], base_url=url)

    async def empty_browser_fetch(url, *, max_pages):
        return []

    text = await collect_website_text(
        "https://x.example",
        crawler=thin_httpx,
        browser_fetch=empty_browser_fetch,
        extractor=lambda p: thin,
        max_pages=5,
    )
    # Even though it's thin, it beats nothing.
    assert "Welcome to our small charity." in text


async def test_playwright_fallback_failure_collapses_to_empty():
    """If both tiers fail, return '' so the generator falls back to CC-only."""

    async def empty_httpx(url, max_pages):
        return CrawlResult(pages=[], base_url=url)

    async def boom_browser(url, *, max_pages):
        raise RuntimeError("Chromium not installed")

    text = await collect_website_text(
        "https://x.example",
        crawler=empty_httpx,
        browser_fetch=boom_browser,
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
