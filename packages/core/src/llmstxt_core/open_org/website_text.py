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
from urllib.parse import urlparse

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

# v0.2.7: the homepage is *always* activity-relevant by definition, but
# ``classify_page_type`` checks URL patterns ahead of the homepage check and
# can label /'s as GET_HELP or DONATE on banner-heavy sites (Shelter).
# Recognise the homepage by URL path so we don't depend on the classifier
# getting it right.
_HOMEPAGE_PATH_MARKERS = {"", "/", "/index.html", "/index.php", "/home"}


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


async def collect_website_pages(
    url: str | None,
    *,
    crawler: CrawlFn | None = None,
    browser_fetch: BrowserFetchFn | None = None,
    extractor: ExtractFn | None = None,
    max_pages: int = 5,
) -> list[ExtractedPage]:
    """Return the relevant ``ExtractedPage`` objects from the most useful
    pages on ``url``.

    Two-tier fetch (httpx → Playwright fallback). Same selection logic as
    :func:`collect_website_text`, but returns the structured pages so callers
    can run additional analysis (e.g. the analyzer for programmes / contact /
    beneficiaries) without re-crawling.
    """
    if not url or not url.strip():
        return []

    crawl_fn = crawler or crawl_site
    extract_fn = extractor or extract_content
    browser_fn = browser_fetch or fetch_with_browser

    normalised_url = _normalise_url(url)

    pages = await _fetch_via_httpx(crawl_fn, normalised_url, max_pages)
    relevant = _select_relevant(pages, extract_fn)

    # Fallback to Playwright when httpx returned nothing usable OR only a
    # low-signal single page. The Mind case is "0 bodies" (httpx hit 403);
    # the Shelter case is "1 thin body" (homepage scraped but no service
    # pages followed). Both want the browser to try.
    if _is_low_signal_pages(relevant):
        log.info("falling back to browser fetch for %s", normalised_url)
        browser_pages = await _fetch_via_browser(browser_fn, normalised_url, max_pages)
        browser_relevant = _select_relevant(browser_pages, extract_fn)
        if _total_body_chars(browser_relevant) > _total_body_chars(relevant):
            relevant = browser_relevant

    return relevant


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

    Thin wrapper around :func:`collect_website_pages`. Kept as the primary
    entry point for the theme extractor and mission rewriter, which only
    need the text.
    """
    pages = await collect_website_pages(
        url,
        crawler=crawler,
        browser_fetch=browser_fetch,
        extractor=extractor,
        max_pages=max_pages,
    )
    bodies = [(p.body_text or "").strip() for p in pages if p.body_text]
    bodies = [b for b in bodies if b]
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


def _is_low_signal_pages(pages: list[ExtractedPage]) -> bool:
    """True when the httpx result is unlikely to give downstream extractors
    enough to work with, so the Playwright fallback should also run."""
    if not pages:
        return True
    if (
        len(pages) <= _LOW_SIGNAL_PAGE_COUNT
        and _total_body_chars(pages) < _LOW_SIGNAL_BODY_THRESHOLD
    ):
        return True
    return False


def _total_body_chars(pages: list[ExtractedPage]) -> int:
    return sum(len(p.body_text or "") for p in pages)


def _select_relevant(
    pages: list[Page], extract_fn: ExtractFn
) -> list[ExtractedPage]:
    """Run the per-page extractor and keep the ones whose page type is in
    ``_RELEVANT_PAGE_TYPES`` (or whose URL path is the homepage). Returns the
    extracted pages so callers can keep ``body_text`` *and* metadata
    (title, page_type, url) for downstream use.
    """
    relevant: list[ExtractedPage] = []
    for page in pages:
        try:
            extracted = extract_fn(page)
        except Exception as exc:  # noqa: BLE001
            log.info("extract failed for %s: %s", getattr(page, "url", "?"), exc)
            continue
        if extracted is None:
            continue
        if extracted.page_type not in _RELEVANT_PAGE_TYPES and not _is_homepage_url(
            getattr(page, "url", None)
        ):
            continue
        if (extracted.body_text or "").strip():
            relevant.append(extracted)
    return relevant


def _is_homepage_url(url: str | None) -> bool:
    """Return True if ``url`` is plausibly the root of a site.

    Independent of ``classify_page_type`` — only the URL matters here. The
    homepage is always activity-relevant for our purposes, so we accept it
    even if the classifier picked a different label based on banner text.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    path = (parsed.path or "").lower()
    return path in _HOMEPAGE_PATH_MARKERS


__all__ = ["collect_website_pages", "collect_website_text"]
