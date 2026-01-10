"""Fetch charity data from the Charity Commission."""

import re
from dataclasses import dataclass
import httpx

from ..extractor import ExtractedPage


@dataclass
class CharityData:
    """Charity data from the Charity Commission."""
    name: str
    number: str
    status: str
    date_registered: str | None
    date_removed: str | None
    latest_income: int | None
    latest_expenditure: int | None
    charitable_objects: str | None
    activities: str | None
    trustees: list[str]
    contact: dict


async def fetch_charity_data(charity_number: str) -> CharityData | None:
    """
    Fetch charity data from the Charity Commission.

    Note: For MVP, this is a placeholder that would integrate with the
    Charity Commission API or scrape their public register.

    API: https://api.charitycommission.gov.uk/
    (Requires registration)

    Args:
        charity_number: The charity registration number

    Returns:
        CharityData if found, None otherwise
    """
    # For MVP, we'll return None
    # In a full implementation, this would:
    # 1. Call the Charity Commission API
    # 2. Parse the response
    # 3. Return structured CharityData

    # Placeholder implementation
    try:
        # The Charity Commission has a public search page we could scrape
        # or use their API if we have credentials
        async with httpx.AsyncClient(timeout=10) as client:
            # This is a simplified example - real implementation would
            # parse the actual API or web page response
            url = f"https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{charity_number}"

            response = await client.get(url)
            if response.status_code == 200:
                # In a real implementation, we would parse the HTML or API response
                # For now, return None as this is marked as "nice to have" for MVP
                return None

    except Exception:
        pass

    return None


def find_charity_number(pages: list[ExtractedPage]) -> str | None:
    """
    Try to find a charity registration number in the extracted pages.

    Looks for patterns like:
    - "Registered charity 1234567"
    - "Charity no. 1234567"
    - "Charity number: 1234567"

    Args:
        pages: List of extracted pages

    Returns:
        Charity number if found, otherwise None
    """
    # First check if any page already has charity_number extracted
    for page in pages:
        if page.charity_number:
            return page.charity_number

    # Common patterns for charity numbers in text
    patterns = [
        r'registered charity\s+(?:number|no\.?|#)?\s*:?\s*(\d{6,7})',
        r'charity\s+(?:number|no\.?|registration|reg\.?)?\s*:?\s*(\d{6,7})',
        r'charity\s+commission\s+(?:number|no\.?)?\s*:?\s*(\d{6,7})',
        r'(?:england\s+(?:and|&)\s+wales|e&w)\s+(?:charity\s+)?(?:number|no\.?)?\s*:?\s*(\d{6,7})',
    ]

    # Search in key pages first (footer, about, contact)
    priority_pages = [
        p for p in pages
        if p.page_type.value in ['about', 'contact', 'home']
    ]

    all_pages_to_search = priority_pages + [p for p in pages if p not in priority_pages]

    for page in all_pages_to_search:
        text_lower = page.body_text.lower()

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                charity_num = match.group(1)
                # Validate it's a reasonable length
                if 6 <= len(charity_num) <= 7:
                    return charity_num

    return None
