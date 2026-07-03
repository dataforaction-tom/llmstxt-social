"""Fetch company data from Companies House.

Companies House provides governance data for UK companies — registered office,
officers/directors, PSC (beneficial ownership), filing history, accounts.
Most medium+ UK charities are companies limited by guarantee; the Charity
Commission enricher's ``company_number`` field bridges to this data.

API: https://api.company-information.service.gov.uk
Auth: HTTP Basic with API key as username, empty password.
Rate limit: 600 requests per 5 minutes.
Docs: https://developer-specs.company-information.service.gov.uk/
"""

import base64
import os
from dataclasses import dataclass, field

import httpx


# Filing types that count as reportable evidence (annual reports / accounts)
_EVIDENCE_FILING_TYPES = {"AA", "AAMD", "CS01", "DS01", "AR01"}


@dataclass
class OfficerRecord:
    """A single officer (director, secretary, etc.)."""

    name: str
    officer_role: str
    appointed_on: str | None
    resigned_on: str | None = None


@dataclass
class FilingRecord:
    """A single filing from the filing history."""

    date: str
    type: str
    description: str
    transaction_id: str


@dataclass
class PSCRecord:
    """A person with significant control."""

    name: str
    natures_of_control: list[str]
    notified_on: str | None
    ceased_on: str | None = None


@dataclass
class CompanyData:
    """Company data from Companies House."""

    name: str
    company_number: str
    status: str
    type: str | None = None
    date_of_creation: str | None = None
    date_of_cessation: str | None = None
    jurisdiction: str | None = None
    sic_codes: list[str] = field(default_factory=list)
    registered_office: dict | None = None
    accounts_next_due: str | None = None
    accounts_overdue: bool | None = None
    last_accounts_made_up_to: str | None = None
    officers: list[OfficerRecord] = field(default_factory=list)
    filing_history: list[FilingRecord] = field(default_factory=list)
    psc: list[PSCRecord] = field(default_factory=list)


_BASE_URL = "https://api.company-information.service.gov.uk"


async def fetch_company_data(
    company_number: str,
    api_key: str | None = None,
) -> CompanyData | None:
    """Fetch company data from Companies House.

    Args:
        company_number: The company registration number (e.g. "01234567").
        api_key: Companies House API key. If None, loads from
            ``COMPANIES_HOUSE_API_KEY`` env var.

    Returns:
        ``CompanyData`` if found, ``None`` if not found or no API key available.
        Network errors degrade to ``None`` rather than raising.
    """
    if api_key is None:
        api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        return None

    # Companies House uses HTTP Basic auth: API key as username, empty password.
    credentials = base64.b64encode(f"{api_key}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 1. Company profile
            resp = await client.get(
                f"{_BASE_URL}/company/{company_number}",
                headers=headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            profile = resp.json()

            # 2. Officers
            officers_resp = await client.get(
                f"{_BASE_URL}/company/{company_number}/officers",
                headers=headers,
            )
            officers_data = officers_resp.json() if officers_resp.status_code == 200 else {}

            # 3. Filing history
            filings_resp = await client.get(
                f"{_BASE_URL}/company/{company_number}/filing-history",
                headers=headers,
            )
            filings_data = filings_resp.json() if filings_resp.status_code == 200 else {}

            # 4. PSC
            psc_resp = await client.get(
                f"{_BASE_URL}/company/{company_number}/persons-with-significant-control",
                headers=headers,
            )
            psc_data = psc_resp.json() if psc_resp.status_code == 200 else {}

            return _parse_company(
                profile,
                officers_data,
                filings_data,
                psc_data,
                company_number,
            )
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def _parse_company(
    profile: dict,
    officers_data: dict,
    filings_data: dict,
    psc_data: dict,
    company_number: str,
) -> CompanyData:
    """Parse the four API responses into a CompanyData."""
    accounts = profile.get("accounts") or {}
    last_accounts = accounts.get("last_accounts") or {}

    officers = [
        OfficerRecord(
            name=o.get("name", ""),
            officer_role=o.get("officer_role", ""),
            appointed_on=o.get("appointed_on"),
            resigned_on=o.get("resigned_on"),
        )
        for o in officers_data.get("items", [])
    ]

    filing_history = [
        FilingRecord(
            date=f.get("date", ""),
            type=f.get("type", ""),
            description=f.get("description", ""),
            transaction_id=f.get("transaction_id", ""),
        )
        for f in filings_data.get("items", [])
    ]

    psc = [
        PSCRecord(
            name=p.get("name", ""),
            natures_of_control=p.get("natures_of_control", []),
            notified_on=p.get("notified_on"),
            ceased_on=p.get("ceased_on"),
        )
        for p in psc_data.get("items", [])
    ]

    return CompanyData(
        name=profile.get("company_name", ""),
        company_number=profile.get("company_number", company_number),
        status=profile.get("company_status", ""),
        type=profile.get("type"),
        date_of_creation=profile.get("date_of_creation"),
        date_of_cessation=profile.get("date_of_cessation"),
        jurisdiction=profile.get("jurisdiction"),
        sic_codes=profile.get("sic_codes", []) or [],
        registered_office=profile.get("registered_office_address"),
        accounts_next_due=accounts.get("next_due"),
        accounts_overdue=accounts.get("overdue"),
        last_accounts_made_up_to=last_accounts.get("made_up_to"),
        officers=officers,
        filing_history=filing_history,
        psc=psc,
    )


def filing_history_to_evidence(
    filings: list[FilingRecord],
    base_url: str = "https://find-and-update.company-information.service.gov.uk",
) -> list[dict]:
    """Map filing history records to evidence[] items for the Open Org profile.

    Only filings that represent reportable documents (accounts, confirmation
    statements) are included. Incorporation and other procedural filings are
    skipped.
    """
    items = []
    for i, f in enumerate(filings):
        if f.type not in _EVIDENCE_FILING_TYPES:
            continue
        url = f"{base_url}/company/{f.transaction_id}/document" if f.transaction_id else None
        items.append(
            {
                "evidence_id": f"ch-filing-{i + 1}",
                "title": f.description,
                "evidence_type": "annual_report",
                "date": f.date,
                "url": url,
                "themes": [],
                "outcomes": [],
            }
        )
    return items