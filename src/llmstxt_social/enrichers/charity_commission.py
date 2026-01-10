"""Fetch charity data from the Charity Commission."""

import os
import re
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

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


async def fetch_charity_data(charity_number: str, api_key: str | None = None) -> CharityData | None:
    """
    Fetch charity data from the Charity Commission.

    Uses the official Charity Commission API if an API key is provided,
    otherwise falls back to scraping the public register.

    API Documentation: https://developer.charitycommission.gov.uk/

    Args:
        charity_number: The charity registration number
        api_key: Optional Charity Commission API key

    Returns:
        CharityData if found, None otherwise
    """
    # Try API first if we have a key
    if api_key:
        data = await _fetch_from_api(charity_number, api_key)
        if data:
            return data

    # Fallback to scraping the public register
    return await _fetch_from_public_register(charity_number)


async def _fetch_from_api(charity_number: str, api_key: str) -> CharityData | None:
    """
    Fetch charity data from the official Charity Commission API.

    API Endpoint: https://api.charitycommission.gov.uk/register/api/
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # The Charity Commission API endpoint
            # Note: The actual API structure may vary - this is based on their documentation
            headers = {
                "Ocp-Apim-Subscription-Key": api_key,
                "Content-Type": "application/json"
            }

            # Try to get charity details
            url = f"https://api.charitycommission.gov.uk/register/api/allcharitydetails/{charity_number}/0"

            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return _parse_api_response(data, charity_number)

    except Exception:
        # Fall back to scraping if API fails
        pass

    return None


def _parse_api_response(data: dict, charity_number: str) -> CharityData | None:
    """Parse the Charity Commission API response."""
    try:
        # Extract main charity information
        charity_info = data.get("charity", {})

        # Get financial information
        financial_info = data.get("financial", {})
        latest_income = None
        latest_expenditure = None

        if financial_info:
            # Get most recent financial year
            latest_income = financial_info.get("income")
            latest_expenditure = financial_info.get("spending")

        # Get trustees
        trustees = []
        trustees_data = data.get("trustees", [])
        for trustee in trustees_data[:10]:  # Limit to first 10
            name = trustee.get("name", "")
            if name:
                trustees.append(name)

        # Get contact information
        contact_info = charity_info.get("contact", {})
        contact = {
            "email": contact_info.get("email"),
            "phone": contact_info.get("phone"),
            "address": contact_info.get("address")
        }

        return CharityData(
            name=charity_info.get("name", "Unknown"),
            number=charity_number,
            status=charity_info.get("registrationStatus", "Unknown"),
            date_registered=charity_info.get("registeredDate"),
            date_removed=charity_info.get("removedDate"),
            latest_income=latest_income,
            latest_expenditure=latest_expenditure,
            charitable_objects=charity_info.get("charitableObjects"),
            activities=charity_info.get("activities"),
            trustees=trustees,
            contact=contact
        )

    except Exception:
        return None


async def _fetch_from_public_register(charity_number: str) -> CharityData | None:
    """
    Scrape charity data from the public Charity Commission register.

    This is a fallback when API access is not available.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "llmstxt-social/0.1.0 (+https://github.com/llmstxt/llmstxt-social)"}
        ) as client:
            # Main charity details page
            url = f"https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{charity_number}"

            response = await client.get(url)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "lxml")

            # Extract charity name
            name = "Unknown"
            name_element = soup.find("h1", class_="charity-heading")
            if name_element:
                name = name_element.get_text(strip=True)

            # Extract registration status
            status = "Registered"
            status_element = soup.select_one(".charity-status")
            if status_element:
                status = status_element.get_text(strip=True)

            # Extract registration date
            date_registered = None
            date_element = soup.find("th", string=re.compile("Registered"))
            if date_element:
                date_td = date_element.find_next_sibling("td")
                if date_td:
                    date_registered = date_td.get_text(strip=True)

            # Extract financial information
            latest_income = None
            latest_expenditure = None

            income_element = soup.find("th", string=re.compile("Income", re.I))
            if income_element:
                income_td = income_element.find_next_sibling("td")
                if income_td:
                    income_text = income_td.get_text(strip=True)
                    # Parse income (e.g., "£123,456")
                    income_clean = re.sub(r'[£,\s]', '', income_text)
                    try:
                        latest_income = int(income_clean)
                    except ValueError:
                        pass

            spending_element = soup.find("th", string=re.compile("Spending", re.I))
            if spending_element:
                spending_td = spending_element.find_next_sibling("td")
                if spending_td:
                    spending_text = spending_td.get_text(strip=True)
                    spending_clean = re.sub(r'[£,\s]', '', spending_text)
                    try:
                        latest_expenditure = int(spending_clean)
                    except ValueError:
                        pass

            # Extract charitable objects (what the charity does)
            charitable_objects = None
            objects_section = soup.find("h3", string=re.compile("What the charity does", re.I))
            if objects_section:
                objects_div = objects_section.find_next("div")
                if objects_div:
                    charitable_objects = objects_div.get_text(separator=" ", strip=True)[:500]

            # Extract activities
            activities = None
            activities_section = soup.find("h3", string=re.compile("How the charity works", re.I))
            if activities_section:
                activities_div = activities_section.find_next("div")
                if activities_div:
                    activities = activities_div.get_text(separator=" ", strip=True)[:500]

            # Extract trustees (would need to visit a separate page or section)
            trustees = []
            trustees_section = soup.find("h2", string=re.compile("Trustees", re.I))
            if trustees_section:
                trustee_list = trustees_section.find_next("ul")
                if trustee_list:
                    for li in trustee_list.find_all("li")[:10]:
                        trustee_name = li.get_text(strip=True)
                        if trustee_name:
                            trustees.append(trustee_name)

            # Extract contact information
            contact = {}

            # Look for contact information in various sections
            contact_section = soup.find("h3", string=re.compile("Contact", re.I))
            if contact_section:
                contact_div = contact_section.find_next("div")
                if contact_div:
                    contact_text = contact_div.get_text()

                    # Extract email
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}', contact_text)
                    if email_match:
                        contact["email"] = email_match.group(0)

                    # Extract phone
                    phone_match = re.search(r'0\d{10}|0\d{4}\s?\d{6}|0\d{3}\s?\d{3}\s?\d{4}', contact_text)
                    if phone_match:
                        contact["phone"] = phone_match.group(0)

            return CharityData(
                name=name,
                number=charity_number,
                status=status,
                date_registered=date_registered,
                date_removed=None,
                latest_income=latest_income,
                latest_expenditure=latest_expenditure,
                charitable_objects=charitable_objects,
                activities=activities,
                trustees=trustees,
                contact=contact
            )

    except Exception:
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
