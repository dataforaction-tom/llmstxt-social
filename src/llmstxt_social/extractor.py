"""Content extraction from HTML pages."""

import re
from dataclasses import dataclass
from enum import Enum
from bs4 import BeautifulSoup, Tag

from .crawler import Page


class PageType(Enum):
    """Classification of page types."""
    HOME = "home"
    ABOUT = "about"
    SERVICES = "services"
    CONTACT = "contact"
    GET_HELP = "get_help"
    VOLUNTEER = "volunteer"
    DONATE = "donate"
    NEWS = "news"
    TEAM = "team"
    POLICY = "policy"
    # Funder-specific
    FUNDING_PRIORITIES = "funding_priorities"
    HOW_TO_APPLY = "how_to_apply"
    PAST_GRANTS = "past_grants"
    ELIGIBILITY = "eligibility"
    OTHER = "other"


@dataclass
class ExtractedPage:
    """Structured content extracted from an HTML page."""
    url: str
    title: str
    description: str | None
    headings: list[str]
    body_text: str
    page_type: PageType
    contact_info: dict | None = None
    charity_number: str | None = None


def extract_content(page: Page) -> ExtractedPage:
    """
    Extract structured content from an HTML page.

    Args:
        page: Page object with HTML content

    Returns:
        ExtractedPage with structured data
    """
    soup = BeautifulSoup(page.html, "lxml")

    # Extract title
    title = page.title or _extract_title(soup)

    # Extract meta description
    description = _extract_meta_description(soup)

    # Extract headings
    headings = _extract_headings(soup)

    # IMPORTANT: Extract charity number from full HTML BEFORE removing footer
    # (Charity numbers are often in footers!)
    full_page_text = soup.get_text(separator=" ", strip=True)
    charity_number = _extract_charity_number(full_page_text)

    # Extract main body text (removes footer, nav, etc.)
    body_text = _extract_body_text(soup)

    # Classify page type
    page_type = classify_page_type(page.url, title, headings, body_text)

    # Extract contact information
    contact_info = _extract_contact_info(body_text, soup)

    return ExtractedPage(
        url=page.url,
        title=title,
        description=description,
        headings=headings,
        body_text=body_text,
        page_type=page_type,
        contact_info=contact_info,
        charity_number=charity_number
    )


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from soup."""
    # Try <title> tag
    title_tag = soup.find("title")
    if title_tag and title_tag.text:
        return title_tag.text.strip()

    # Fallback to <h1>
    h1_tag = soup.find("h1")
    if h1_tag:
        return h1_tag.get_text(strip=True)

    return "Untitled"


def _extract_meta_description(soup: BeautifulSoup) -> str | None:
    """Extract meta description."""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()

    # Try og:description
    meta_og = soup.find("meta", attrs={"property": "og:description"})
    if meta_og and meta_og.get("content"):
        return meta_og["content"].strip()

    return None


def _extract_headings(soup: BeautifulSoup) -> list[str]:
    """Extract all h1 and h2 headings."""
    headings = []

    for tag_name in ["h1", "h2"]:
        for heading in soup.find_all(tag_name):
            text = heading.get_text(strip=True)
            if text:
                headings.append(text)

    return headings


def _extract_body_text(soup: BeautifulSoup) -> str:
    """Extract main body text, stripping navigation, footer, scripts, etc."""
    # Remove unwanted elements
    for element in soup.find_all(["script", "style", "nav", "header", "footer", "iframe", "noscript"]):
        element.decompose()

    # Try to find main content area
    main_content = None

    # Look for common main content containers
    for selector in ["main", "article", '[role="main"]', "#content", "#main", ".content", ".main"]:
        main_content = soup.select_one(selector)
        if main_content:
            break

    # If no main content found, use body
    if not main_content:
        main_content = soup.find("body")

    if not main_content:
        main_content = soup

    # Extract text
    text = main_content.get_text(separator=" ", strip=True)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def _extract_contact_info(body_text: str, soup: BeautifulSoup) -> dict | None:
    """Extract contact information from text and HTML."""
    contact = {}

    # Email regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, body_text)
    if emails:
        # Filter out common non-contact emails
        filtered_emails = [e for e in emails if not any(
            skip in e.lower() for skip in ['example.com', 'domain.com', 'email.com']
        )]
        if filtered_emails:
            contact['email'] = filtered_emails[0]

    # Also check for mailto links
    if 'email' not in contact:
        mailto_link = soup.find("a", href=re.compile(r'^mailto:'))
        if mailto_link:
            email = mailto_link['href'].replace('mailto:', '').split('?')[0]
            contact['email'] = email

    # UK phone number regex (simplified)
    phone_pattern = r'(?:(?:\+44\s?|0)(?:\d\s?){10})'
    phones = re.findall(phone_pattern, body_text)
    if phones:
        contact['phone'] = phones[0].strip()

    # Try to find address (very basic)
    # Look for UK postcode pattern
    postcode_pattern = r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b'
    postcodes = re.findall(postcode_pattern, body_text)
    if postcodes:
        contact['postcode'] = postcodes[0]

    return contact if contact else None


def _extract_charity_number(text: str) -> str | None:
    """Extract charity registration number from text."""
    # Patterns for charity numbers (UK charities are 6-7 digits)
    # These patterns handle common variations including periods, colons, and spaces
    patterns = [
        # "Registered Charity No. 1094112" or "Registered Charity Number 1094112"
        r'registered\s+charity\s+(?:number|no\.?|num\.?|#)?\s*:?\s*(\d{6,7})',
        # "Charity No: 1094112" or "Charity Number: 1094112"
        r'charity\s+(?:number|no\.?|num\.?|#|registration|reg\.?)\s*:?\s*(\d{6,7})',
        # "Charity Commission No. 1094112"
        r'charity\s+commission\s+(?:number|no\.?|#)?\s*:?\s*(\d{6,7})',
        # "England and Wales 1094112" or "E&W 1094112"
        r'(?:england\s+(?:and|&)\s+wales|e\s*&\s*w)\s+(?:charity\s+)?(?:number|no\.?|#)?\s*:?\s*(\d{6,7})',
        # "Reg. Charity 1094112"
        r'reg\.?\s+charity\s*:?\s*(\d{6,7})',
        # Fallback: Just "Charity: 1094112" with optional colon
        r'charity\s*:?\s+(\d{6,7})\b',
    ]

    text_lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            number = match.group(1)
            # Validate it's 6 or 7 digits
            if 6 <= len(number) <= 7:
                return number

    return None


def classify_page_type(url: str, title: str, headings: list[str], body_text: str) -> PageType:
    """
    Classify a page into one of the defined types.

    Uses URL patterns, title, headings, and body text to determine type.

    Args:
        url: Page URL
        title: Page title
        headings: List of headings
        body_text: Main body text

    Returns:
        PageType classification
    """
    url_lower = url.lower()
    title_lower = title.lower()
    headings_text = " ".join(headings).lower()
    body_sample = body_text[:1000].lower()  # First 1000 chars

    # Combine all text for keyword matching
    all_text = f"{url_lower} {title_lower} {headings_text} {body_sample}"

    # URL patterns (most specific first)
    url_patterns = {
        PageType.CONTACT: ['/contact', '/get-in-touch', '/reach-us'],
        PageType.ABOUT: ['/about', '/who-we-are', '/our-story', '/mission'],
        PageType.SERVICES: ['/services', '/what-we-do', '/our-work', '/programmes', '/programs'],
        PageType.GET_HELP: ['/get-help', '/support', '/access', '/referral'],
        PageType.VOLUNTEER: ['/volunteer', '/get-involved', '/join-us'],
        PageType.DONATE: ['/donate', '/support-us', '/give', '/fundrais'],
        PageType.NEWS: ['/news', '/blog', '/stories', '/updates', '/latest'],
        PageType.TEAM: ['/team', '/staff', '/people', '/trustees', '/our-team'],
        PageType.POLICY: ['/policy', '/policies', '/privacy', '/safeguarding'],
        PageType.FUNDING_PRIORITIES: ['/priorities', '/funding-priorities', '/what-we-fund', '/themes'],
        PageType.HOW_TO_APPLY: ['/apply', '/application', '/how-to-apply', '/guidelines'],
        PageType.PAST_GRANTS: ['/grants', '/past-grants', '/who-we-fund', '/grantees'],
        PageType.ELIGIBILITY: ['/eligibility', '/who-can-apply', '/criteria'],
    }

    # Check URL patterns
    for page_type, patterns in url_patterns.items():
        if any(pattern in url_lower for pattern in patterns):
            return page_type

    # Keyword patterns for content
    keyword_patterns = {
        PageType.CONTACT: ['contact us', 'get in touch', 'email us', 'phone us'],
        PageType.ABOUT: ['about us', 'who we are', 'our mission', 'our story', 'founded'],
        PageType.SERVICES: ['our services', 'what we do', 'we provide', 'we offer'],
        PageType.GET_HELP: ['get help', 'need support', 'access support', 'how to access'],
        PageType.VOLUNTEER: ['volunteer', 'volunteering', 'become a volunteer'],
        PageType.DONATE: ['donate', 'donation', 'support our work', 'make a gift'],
        PageType.NEWS: ['latest news', 'recent posts', 'blog'],
        PageType.TEAM: ['our team', 'meet the team', 'staff', 'trustees'],
        PageType.FUNDING_PRIORITIES: ['funding priorities', 'what we fund', 'our themes'],
        PageType.HOW_TO_APPLY: ['how to apply', 'application process', 'submit an application'],
        PageType.PAST_GRANTS: ['past grants', 'previous grants', 'who we have funded'],
        PageType.ELIGIBILITY: ['eligibility', 'who can apply', 'eligible organisations'],
    }

    # Check keyword patterns
    for page_type, keywords in keyword_patterns.items():
        if any(keyword in all_text for keyword in keywords):
            return page_type

    # Check if it's the homepage (root path or index)
    if url_lower.rstrip('/').endswith(('/', '/index.html', '/index.php', '/home')):
        path = url_lower.split('/')[-1] if '/' in url_lower else ''
        if not path or path in ['index.html', 'index.php', 'home']:
            return PageType.HOME

    return PageType.OTHER


def find_charity_number(pages: list[ExtractedPage]) -> str | None:
    """
    Try to find a charity registration number across all pages.

    Args:
        pages: List of extracted pages

    Returns:
        Charity number if found, otherwise None
    """
    for page in pages:
        if page.charity_number:
            return page.charity_number

    return None
