"""Crawl a charity's website and concatenate the body text we care about.

Used by the Open Org profile generator (Phase 1.5 / v0.2.1) to augment the
theme extractor with content from the charity's own site. CC
``who_what_where`` text alone is too sparse for orgs like Trussell Trust
(missing food_access) and Shelter (missing housing_and_homelessness) — the
v0.1 baseline made the gap obvious.

Failures (DNS, timeout, malformed HTML) collapse to an empty string so the
generator falls back to CC-only data rather than failing the whole profile.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from llmstxt_core.crawler import CrawlResult, Page, crawl_site
from llmstxt_core.extractor import ExtractedPage, PageType, extract_content
from llmstxt_core.playwright_fetch import fetch_with_browser


log = logging.getLogger(__name__)


# Page types worth feeding to the theme extractor. Excludes pages that are
# mostly boilerplate (DONATE / CONTACT / TEAM / POLICY) or noise.
_RELEVANT_PAGE_TYPES = {
    PageType.HOME,
    PageType.ABOUT,
    PageType.SERVICES,
    PageType.GET_HELP,
    PageType.VOLUNTEER,
}

# v0.2.6 follow-up: trigger Playwright when httpx returned content that is
# probably the homepage alone with no service-page detail. The Shelter case
# in baseline_v0.2 had httpx return a 24KB homepage that extracted to one
# short HOME body — passing the page-type filter but lacking the activity
# descriptions the theme extractor needs.
_LOW_SIGNAL_BODY_THRESHOLD = 1500
_LOW_SIGNAL_PAGE_COUNT = 1


CrawlFn = Callable[..., Awaitable[CrawlResult]]
ExtractFn = Callable[..., "ExtractedPage | None"]
BrowserFetchFn = Callable[..., Awaitable["list[Page]"]]


def _normalise_url(url: str) -> str:
    """Add an ``https://`` scheme when the CC API returns bare hostnames.

    The Charity Commission API often gives back ``www.example.org`` with no
    scheme; httpx then rejects it. This single defensive step makes the
    common case work without forcing every CC consumer to clean URLs.
    """
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate.lstrip("/")
    return candidate


async def collect_website_text(
    url: str | None,
    *,
    crawler: CrawlFn | None = None,
    browser_fetch: BrowserFetchFn | None = None,
    extractor: ExtractFn | None = None,
    max_pages: int = 5,
    max_chars: int = 20_000,
) -> str:
    """Return concatenated body text from the most relevant pages on ``url``.

    Two-tier fetch:
      1. Lightweight httpx crawler (fast, free, ~200ms/page).
      2. Playwright fallback when (1) errors, returns no pages, or returns
         only pages that fail the page-type filter. Slower (~2-5s/page) but
         renders JS and survives basic bot defences (the v0.2 baseline showed
         Mind's site 403's the httpx crawler).

    ``crawler``, ``browser_fetch``, and ``extractor`` are injectable for tests.
    Production callers use the package defaults (``crawl_site``,
    ``fetch_with_browser``, ``extract_content``).

    Returns ``""`` on any failure so the calling generator can fall back to
    CC-only theme extraction without raising.
    """
    if not url or not url.strip():
        return ""

    crawl_fn = crawler or crawl_site
    extract_fn = extractor or extract_content
    browser_fn = browser_fetch or fetch_with_browser

    normalised_url = _normalise_url(url)

    pages = await _fetch_via_httpx(crawl_fn, normalised_url, max_pages)
    bodies = _extract_relevant_bodies(pages, extract_fn)

    # Fallback to Playwright when httpx returned nothing usable OR only a
    # low-signal single page. The Mind case is "0 bodies" (httpx hit 403);
    # the Shelter case is "1 thin body" (homepage scraped but no service
    # pages followed). Both want the browser to try.
    if _is_low_signal(bodies):
        log.info("falling back to browser fetch for %s", normalised_url)
        browser_pages = await _fetch_via_browser(browser_fn, normalised_url, max_pages)
        browser_bodies = _extract_relevant_bodies(browser_pages, extract_fn)
        # Use whichever path produced more text — Playwright should normally
        # win, but if it returns nothing (Mind-class 403 to the browser too)
        # we keep the thin httpx body rather than throwing both away.
        if _total_chars(browser_bodies) > _total_chars(bodies):
            bodies = browser_bodies

    if not bodies:
        return ""

    text = "\n\n".join(bodies)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


async def _fetch_via_httpx(
    crawl_fn: CrawlFn, url: str, max_pages: int
) -> list[Page]:
    try:
        crawl_result = await crawl_fn(url, max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001 — broad on purpose; never break generation
        log.info("httpx crawl failed for %s: %s", url, exc)
        return []
    return list(getattr(crawl_result, "pages", None) or [])


async def _fetch_via_browser(
    browser_fn: BrowserFetchFn, url: str, max_pages: int
) -> list[Page]:
    try:
        return await browser_fn(url, max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001
        log.info("browser fetch failed for %s: %s", url, exc)
        return []


def _is_low_signal(bodies: list[str]) -> bool:
    """True when the httpx result is unlikely to give the theme extractor
    enough to work with, so the Playwright fallback should also run."""
    if not bodies:
        return True
    if (
        len(bodies) <= _LOW_SIGNAL_PAGE_COUNT
        and _total_chars(bodies) < _LOW_SIGNAL_BODY_THRESHOLD
    ):
        return True
    return False


def _total_chars(bodies: list[str]) -> int:
    return sum(len(b) for b in bodies)


def _extract_relevant_bodies(
    pages: list[Page], extract_fn: ExtractFn
) -> list[str]:
    bodies: list[str] = []
    for page in pages:
        try:
            extracted = extract_fn(page)
        except Exception as exc:  # noqa: BLE001
            log.info("extract failed for %s: %s", getattr(page, "url", "?"), exc)
            continue
        if extracted is None:
            continue
        if extracted.page_type not in _RELEVANT_PAGE_TYPES:
            continue
        body = (extracted.body_text or "").strip()
        if body:
            bodies.append(body)
    return bodies


__all__ = ["collect_website_text"]
