"""Playwright-based crawler for JavaScript-heavy websites."""

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from playwright.async_api import async_playwright, Page as PlaywrightPage, Browser
from bs4 import BeautifulSoup

from .crawler import Page, CrawlResult


class PlaywrightCrawler:
    """Asynchronous web crawler using Playwright for JavaScript-rendered sites."""

    def __init__(
        self,
        max_pages: int = 30,
        timeout: int = 30,
        respect_robots: bool = True,
        rate_limit: float = 2.0,  # Slower for JS rendering
        headless: bool = True,
    ):
        self.max_pages = max_pages
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.respect_robots = respect_robots
        self.rate_limit = rate_limit
        self.headless = headless
        self.visited_urls: set[str] = set()
        self.robot_parser: RobotFileParser | None = None
        self.browser: Browser | None = None

    async def crawl_site(self, url: str) -> CrawlResult:
        """
        Crawl a website using Playwright (for JavaScript-rendered sites).

        Args:
            url: Starting URL (should be the homepage)

        Returns:
            CrawlResult containing all fetched pages
        """
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        result = CrawlResult(base_url=base_url)

        async with async_playwright() as p:
            # Launch browser
            self.browser = await p.chromium.launch(headless=self.headless)

            try:
                # Step 1: Fetch robots.txt (using simple HTTP, not Playwright)
                if self.respect_robots:
                    result.robots_txt = await self._fetch_robots_txt(base_url)

                # Step 2: Try to discover URLs
                # For JavaScript sites, we need to actually render the homepage to find links
                urls_to_crawl = await self._discover_urls_playwright(url, base_url)

                # Also try sitemap
                sitemap_urls = await self._try_sitemap(base_url)
                if sitemap_urls:
                    urls_to_crawl.extend(sitemap_urls)
                    result.sitemap_urls = sitemap_urls

                # Deduplicate
                urls_to_crawl = list(set(urls_to_crawl))[:self.max_pages]

                # Step 3: Fetch each page with Playwright
                for page_url in urls_to_crawl:
                    if len(result.pages) >= self.max_pages:
                        break

                    if not self._can_fetch(page_url):
                        continue

                    page = await self._fetch_page_playwright(page_url)
                    if page:
                        result.pages.append(page)

                    # Rate limiting
                    await asyncio.sleep(self.rate_limit)

            finally:
                await self.browser.close()

        return result

    async def _fetch_robots_txt(self, base_url: str) -> str | None:
        """Fetch robots.txt using simple HTTP."""
        import httpx

        robots_url = f"{base_url}/robots.txt"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    robots_content = response.text
                    self.robot_parser = RobotFileParser()
                    self.robot_parser.parse(robots_content.splitlines())
                    return robots_content
        except Exception:
            pass
        return None

    async def _try_sitemap(self, base_url: str) -> list[str]:
        """Try to fetch sitemap (using simple HTTP)."""
        import httpx

        sitemap_locations = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
        ]

        for sitemap_url in sitemap_locations:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(sitemap_url)
                    if response.status_code == 200:
                        return self._parse_sitemap(response.text)
            except Exception:
                continue

        return []

    def _parse_sitemap(self, sitemap_xml: str) -> list[str]:
        """Parse sitemap XML."""
        urls = []
        soup = BeautifulSoup(sitemap_xml, "lxml-xml")

        for loc in soup.find_all("loc"):
            url = loc.text.strip()
            if not any(url.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".css", ".js"]):
                urls.append(url)

        return urls

    async def _discover_urls_playwright(self, start_url: str, base_url: str) -> list[str]:
        """Discover URLs by rendering the homepage and extracting links."""
        urls = {start_url}

        try:
            context = await self.browser.new_context(
                user_agent="llmstxt-social/0.2.0 (+https://github.com/llmstxt/llmstxt-social)"
            )
            page = await context.new_page()

            # Navigate to homepage
            await page.goto(start_url, wait_until="networkidle", timeout=self.timeout)

            # Wait for dynamic content to load
            await asyncio.sleep(2)

            # Extract all links
            links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(a => a.href);
                }
            """)

            for link in links:
                absolute_url = urljoin(start_url, link)
                if self._is_internal_url(absolute_url, base_url):
                    if not any(absolute_url.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif"]):
                        urls.add(absolute_url)

            await context.close()

        except Exception:
            pass

        return list(urls)

    async def _fetch_page_playwright(self, url: str) -> Page | None:
        """Fetch a single page using Playwright."""
        try:
            context = await self.browser.new_context(
                user_agent="llmstxt-social/0.2.0 (+https://github.com/llmstxt/llmstxt-social)"
            )
            page = await context.new_page()

            # Navigate to page
            response = await page.goto(url, wait_until="networkidle", timeout=self.timeout)

            if not response or response.status != 200:
                await context.close()
                return None

            # Wait for dynamic content
            await asyncio.sleep(1)

            # Get the rendered HTML
            html = await page.content()

            # Get the title
            title = await page.title()

            await context.close()

            return Page(
                url=url,
                title=title,
                html=html,
                status_code=response.status
            )

        except Exception:
            return None

    def _is_internal_url(self, url: str, base_url: str) -> bool:
        """Check if a URL is internal to the base domain."""
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)
        return parsed_url.netloc == parsed_base.netloc

    def _can_fetch(self, url: str) -> bool:
        """Check if we can fetch a URL according to robots.txt."""
        if not self.respect_robots or not self.robot_parser:
            return True
        return self.robot_parser.can_fetch("*", url)


async def crawl_site_with_playwright(
    url: str,
    max_pages: int = 30,
    timeout: int = 30,
    respect_robots: bool = True,
    headless: bool = True,
) -> CrawlResult:
    """
    Crawl a website using Playwright (for JavaScript-rendered sites).

    Args:
        url: Website URL to crawl (should be homepage)
        max_pages: Maximum number of pages to fetch
        timeout: Request timeout in seconds
        respect_robots: Whether to respect robots.txt
        headless: Whether to run browser in headless mode

    Returns:
        CrawlResult with all fetched pages
    """
    crawler = PlaywrightCrawler(
        max_pages=max_pages,
        timeout=timeout,
        respect_robots=respect_robots,
        headless=headless,
    )
    return await crawler.crawl_site(url)
