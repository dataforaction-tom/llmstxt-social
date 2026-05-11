"""Playwright-backed page fetch — fallback for the Open Org website crawl.

Thin wrapper around :class:`crawler_playwright.PlaywrightCrawler`. Lives at
the core layer (parallel to ``crawler.py``) so other consumers can use it
too. The Open Org generator wires it up via
``website_text.collect_website_text``.

Used as the second tier when the lightweight httpx crawler hits a 403 or
returns no usable pages — the v0.2 baseline showed Mind's site blocks bare
``httpx`` requests but renders fine in a real browser.
"""

from __future__ import annotations

import logging
from typing import Any

from llmstxt_core.crawler import Page
from llmstxt_core.crawler_playwright import PlaywrightCrawler


log = logging.getLogger(__name__)


async def fetch_with_browser(
    url: str,
    *,
    max_pages: int = 5,
    timeout: int = 30,
    crawler_factory: Any = None,
) -> list[Page]:
    """Render ``url`` (and a few same-host links) via headless Chromium.

    Returns ``Page`` objects compatible with :func:`extractor.extract_content`.
    Errors propagate so the caller (``collect_website_text``) can log + fall
    back to CC-only theme extraction.

    ``crawler_factory`` is injectable for tests; defaults to constructing a
    fresh :class:`PlaywrightCrawler` per call.
    """
    factory = crawler_factory or (
        lambda: PlaywrightCrawler(
            max_pages=max_pages,
            timeout=timeout,
            respect_robots=True,
            headless=True,
        )
    )
    crawler = factory()
    result = await crawler.crawl_site(url)
    return list(getattr(result, "pages", None) or [])


__all__ = ["fetch_with_browser"]
