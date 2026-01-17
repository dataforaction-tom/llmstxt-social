"""Website crawling functionality."""

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup


@dataclass
class Page:
    """Represents a single crawled web page."""
    url: str
    title: str
    html: str
    status_code: int


@dataclass
class CrawlResult:
    """Results from crawling a website."""
    base_url: str
    pages: list[Page] = field(default_factory=list)
    robots_txt: str | None = None
    sitemap_urls: list[str] = field(default_factory=list)


class WebCrawler:
    """Asynchronous web crawler with respect for robots.txt."""

    def __init__(
        self,
        max_pages: int = 30,
        timeout: int = 30,
        respect_robots: bool = True,
        rate_limit: float = 1.0,
    ):
        self.max_pages = max_pages
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.rate_limit = rate_limit
        self.visited_urls: set[str] = set()
        self.robot_parser: RobotFileParser | None = None

    async def crawl_site(self, url: str) -> CrawlResult:
        """
        Crawl a website starting from the given URL.

        Args:
            url: Starting URL (should be the homepage)

        Returns:
            CrawlResult containing all fetched pages
        """
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        result = CrawlResult(base_url=base_url)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "llmstxt-social/0.1.0 (+https://github.com/llmstxt/llmstxt-social)"}
        ) as client:
            # Step 1: Fetch robots.txt
            if self.respect_robots:
                result.robots_txt = await self._fetch_robots_txt(client, base_url)

            # Step 2: Try to find and parse sitemap.xml
            sitemap_urls = await self._fetch_sitemap_urls(client, base_url)
            result.sitemap_urls = sitemap_urls

            # Step 3: Determine URLs to crawl
            urls_to_crawl = []
            if sitemap_urls:
                # Use sitemap URLs
                urls_to_crawl = sitemap_urls[:self.max_pages]
            else:
                # Discover URLs by crawling from homepage
                urls_to_crawl = await self._discover_urls(client, url, base_url)

            # Step 4: Fetch each page
            print(f"URLs to crawl: {len(urls_to_crawl)}")
            for page_url in urls_to_crawl[:self.max_pages]:
                if len(result.pages) >= self.max_pages:
                    break

                if not self._can_fetch(page_url):
                    print(f"  Skipping (robots.txt): {page_url}")
                    continue

                page = await self._fetch_page(client, page_url)
                if page:
                    result.pages.append(page)
                    print(f"  Fetched: {page_url} ({len(page.html)} bytes)")
                else:
                    print(f"  Failed to fetch: {page_url}")

                # Rate limiting
                await asyncio.sleep(self.rate_limit)

        return result

    async def _fetch_robots_txt(self, client: httpx.AsyncClient, base_url: str) -> str | None:
        """Fetch and parse robots.txt."""
        robots_url = f"{base_url}/robots.txt"
        try:
            response = await client.get(robots_url)
            if response.status_code == 200:
                robots_content = response.text
                self.robot_parser = RobotFileParser()
                self.robot_parser.parse(robots_content.splitlines())
                return robots_content
        except Exception:
            pass
        return None

    async def _fetch_sitemap_urls(self, client: httpx.AsyncClient, base_url: str) -> list[str]:
        """Try to fetch URLs from sitemap.xml."""
        sitemap_locations = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemap-index.xml",
        ]

        for sitemap_url in sitemap_locations:
            try:
                response = await client.get(sitemap_url)
                if response.status_code == 200:
                    return await self._parse_sitemap(client, response.text)
            except Exception:
                continue

        return []

    async def _parse_sitemap(self, client: httpx.AsyncClient, sitemap_xml: str) -> list[str]:
        """Parse sitemap XML and extract URLs. Handles sitemap index files recursively."""
        urls = []
        sub_sitemaps = []
        soup = BeautifulSoup(sitemap_xml, "lxml-xml")

        # Check for sitemap index (contains <sitemap> elements)
        for sitemap in soup.find_all("sitemap"):
            loc = sitemap.find("loc")
            if loc:
                sub_sitemaps.append(loc.text.strip())

        # If this is a sitemap index, recursively fetch sub-sitemaps
        if sub_sitemaps:
            print(f"  Found sitemap index with {len(sub_sitemaps)} sub-sitemaps")
            for sub_url in sub_sitemaps:
                try:
                    print(f"    Fetching sub-sitemap: {sub_url}")
                    response = await client.get(sub_url)
                    if response.status_code == 200:
                        sub_urls = await self._parse_sitemap(client, response.text)
                        urls.extend(sub_urls)
                except Exception as e:
                    print(f"    Error fetching sub-sitemap {sub_url}: {e}")
                    continue
        else:
            # Regular sitemap - extract URLs
            for loc in soup.find_all("loc"):
                url = loc.text.strip()
                # Skip non-HTML resources, XML files, and external image hosts
                if any(url.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".css", ".js", ".xml"]):
                    continue
                # Skip common image hosting domains
                if any(domain in url for domain in ["images.unsplash.com", "cdn.pixabay.com", "cloudinary.com", "imgur.com"]):
                    continue
                urls.append(url)

        print(f"  Parsed sitemap: found {len(urls)} page URLs")
        if urls:
            print(f"  First few URLs: {urls[:5]}")

        return urls

    async def _discover_urls(
        self,
        client: httpx.AsyncClient,
        start_url: str,
        base_url: str
    ) -> list[str]:
        """Discover URLs by following links from the homepage."""
        urls = {start_url}
        queue = [start_url]
        depth = 0
        max_depth = 2

        while queue and depth < max_depth and len(urls) < self.max_pages * 2:
            next_queue = []

            for url in queue:
                if url in self.visited_urls:
                    continue

                self.visited_urls.add(url)

                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                    # Only process HTML
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue

                    soup = BeautifulSoup(response.text, "lxml")

                    # Extract links
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        absolute_url = urljoin(url, href)

                        # Only include internal links
                        if self._is_internal_url(absolute_url, base_url):
                            # Skip non-HTML resources
                            if not any(absolute_url.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".css", ".js"]):
                                if absolute_url not in urls:
                                    urls.add(absolute_url)
                                    next_queue.append(absolute_url)

                    await asyncio.sleep(self.rate_limit)

                except Exception:
                    continue

            queue = next_queue
            depth += 1

        return list(urls)

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

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> Page | None:
        """Fetch a single page."""
        try:
            response = await client.get(url)

            # Only process successful HTML responses
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                print(f"    Non-HTML content-type: {content_type} for {url}")
                return None

            if response.status_code != 200:
                print(f"    Non-200 status: {response.status_code} for {url}")
                return None

            soup = BeautifulSoup(response.text, "lxml")
            title = ""

            # Try to get title
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.text.strip()
            else:
                # Fallback to h1
                h1_tag = soup.find("h1")
                if h1_tag:
                    title = h1_tag.text.strip()

            return Page(
                url=url,
                title=title,
                html=response.text,
                status_code=response.status_code
            )

        except Exception as e:
            print(f"    Exception fetching {url}: {e}")
            return None


async def crawl_site(
    url: str,
    max_pages: int = 30,
    timeout: int = 30,
    respect_robots: bool = True
) -> CrawlResult:
    """
    Crawl a website starting from the given URL.

    Args:
        url: Website URL to crawl (should be homepage)
        max_pages: Maximum number of pages to fetch
        timeout: Request timeout in seconds
        respect_robots: Whether to respect robots.txt

    Returns:
        CrawlResult with all fetched pages
    """
    crawler = WebCrawler(
        max_pages=max_pages,
        timeout=timeout,
        respect_robots=respect_robots
    )
    return await crawler.crawl_site(url)
