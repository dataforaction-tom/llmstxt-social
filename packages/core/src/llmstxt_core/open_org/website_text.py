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

from llmstxt_core.crawler import CrawlResult, crawl_site
from llmstxt_core.extractor import ExtractedPage, PageType, extract_content


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


CrawlFn = Callable[..., Awaitable[CrawlResult]]
ExtractFn = Callable[..., "ExtractedPage | None"]


async def collect_website_text(
    url: str | None,
    *,
    crawler: CrawlFn | None = None,
    extractor: ExtractFn | None = None,
    max_pages: int = 5,
    max_chars: int = 20_000,
) -> str:
    """Return concatenated body text from the most relevant pages on ``url``.

    Crawls up to ``max_pages`` pages; filters to page types likely to describe
    activities (home, about, services, get help, volunteer); concatenates body
    text from the resulting pages; truncates to ``max_chars``.

    ``crawler`` and ``extractor`` are injectable for tests. Production callers
    use the package defaults (``crawl_site`` + ``extract_content``).

    Returns ``""`` on any failure so the calling generator can fall back to
    CC-only theme extraction without raising.
    """
    if not url or not url.strip():
        return ""

    crawl_fn = crawler or crawl_site
    extract_fn = extractor or extract_content

    try:
        crawl_result = await crawl_fn(url.strip(), max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001 — broad on purpose; never break generation
        log.info("website crawl failed for %s: %s", url, exc)
        return ""

    pages = getattr(crawl_result, "pages", None) or []
    if not pages:
        return ""

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

    if not bodies:
        return ""

    text = "\n\n".join(bodies)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


__all__ = ["collect_website_text"]
