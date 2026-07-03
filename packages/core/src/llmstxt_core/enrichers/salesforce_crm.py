"""Salesforce CRM enricher (Pattern A — read-only enrichment).

Salesforce Nonprofit Cloud stores org accounts, grants/opportunities, and
contacts. This enricher reads data via the Salesforce REST API (v60.0) using
OAuth2 bearer-token auth, then maps grants and contacts to Open Org
``evidence[]`` items.

API reference:
    - GET /sobjects/Account/{id}  — org account detail
    - GET /query/?q={soql}        — SOQL query (opportunities, contacts)
    - Pagination via ``nextRecordsUrl`` in query responses

Auth: ``Authorization: Bearer {access_token}`` header on every request.

This is **Pattern A** (read-only): we never create or update Salesforce
records, only enrich the Open Org profile from what's already there.
"""

from dataclasses import dataclass
from datetime import date as _date
from typing import Any, Callable

import httpx


_API_VERSION = "v60.0"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SalesforceAccount:
    """A Salesforce Account record (the nonprofit org)."""

    id: str
    name: str
    type: str | None = None
    billing_address: dict[str, Any] | None = None
    website: str | None = None
    description: str | None = None
    industry: str | None = None


@dataclass
class SalesforceOpportunity:
    """A Salesforce Opportunity record (grant, donation, or program).

    ``type`` is typically one of: ``'Grant'``, ``'Donation'``, ``'Program'``.
    Only ``Grant`` opportunities map to ``outcome_data`` evidence.
    """

    id: str
    name: str
    amount: float
    stage: str
    close_date: str
    type: str
    account_id: str


@dataclass
class SalesforceContact:
    """A Salesforce Contact record (relationship evidence)."""

    id: str
    name: str
    email: str | None
    role: str | None
    account_id: str


# ---------------------------------------------------------------------------
# SalesforceClient
# ---------------------------------------------------------------------------


class SalesforceClient:
    """Async client for the Salesforce REST API (read-only enrichment).

    Args:
        access_token: OAuth2 access token sent as a Bearer credential.
        instance_url: Salesforce instance URL, e.g.
            ``https://riverside.my.salesforce.com``.
        http_client_factory: Optional callable that returns an async context
            manager (e.g. ``httpx.AsyncClient``). Used for test injection.
    """

    def __init__(
        self,
        access_token: str,
        instance_url: str,
        http_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._access_token = access_token
        # Strip trailing slash so we can join cleanly
        self._instance_url = instance_url.rstrip("/")
        self._base_url = f"{self._instance_url}/services/data/{_API_VERSION}"
        self._http_client_factory = http_client_factory

    # -- public API ---------------------------------------------------------

    async def get_account(self, account_id: str) -> SalesforceAccount | None:
        """Fetch a single Account by ID.

        Returns ``None`` on 404 or network error.
        """
        url = f"{self._base_url}/sobjects/Account/{account_id}"
        data = await self._get_json(url)
        if data is None:
            return None
        return self._parse_account(data)

    async def get_opportunities(self, account_id: str) -> list[SalesforceOpportunity]:
        """Fetch all Opportunity records for an Account via SOQL.

        Returns an empty list on error.
        """
        soql = (
            "SELECT Id, Name, Amount, StageName, CloseDate, Type, AccountId "
            f"FROM Opportunity WHERE AccountId = '{account_id}'"
        )
        records = await self.query(soql)
        return [self._parse_opportunity(r) for r in records]

    async def get_contacts(self, account_id: str) -> list[SalesforceContact]:
        """Fetch all Contact records for an Account via SOQL.

        Returns an empty list on error.
        """
        soql = (
            "SELECT Id, Name, Email, Role__c, AccountId "
            f"FROM Contact WHERE AccountId = '{account_id}'"
        )
        records = await self.query(soql)
        return [self._parse_contact(r) for r in records]

    async def query(self, soql: str) -> list[dict]:
        """Execute a raw SOQL query and return the list of record dicts.

        Follows ``nextRecordsUrl`` pagination automatically.
        Returns an empty list on error.
        """
        url = f"{self._base_url}/query/"
        params = {"q": soql}
        records: list[dict] = []
        try:
            async with self._make_client() as client:
                resp = await client.get(url, params=params, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                records.extend(data.get("records", []))

                # Follow pagination via nextRecordsUrl
                next_url = data.get("nextRecordsUrl")
                while next_url:
                    full_next = (
                        f"{self._instance_url}{next_url}"
                        if next_url.startswith("/")
                        else next_url
                    )
                    resp = await client.get(full_next, headers=self._headers())
                    resp.raise_for_status()
                    data = resp.json()
                    records.extend(data.get("records", []))
                    next_url = data.get("nextRecordsUrl")
        except (httpx.HTTPError, KeyError, ValueError):
            return []
        return records

    # -- internals ----------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    def _make_client(self) -> Any:
        if self._http_client_factory is not None:
            return self._http_client_factory()
        return httpx.AsyncClient(timeout=30)

    async def _get_json(self, url: str) -> dict | None:
        """GET a URL and return the JSON body, or ``None`` on 404 / error."""
        try:
            async with self._make_client() as client:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, KeyError, ValueError):
            return None

    # -- parsers ------------------------------------------------------------

    @staticmethod
    def _parse_account(data: dict) -> SalesforceAccount:
        return SalesforceAccount(
            id=data.get("Id", ""),
            name=data.get("Name", ""),
            type=data.get("Type"),
            billing_address=data.get("BillingAddress"),
            website=data.get("Website"),
            description=data.get("Description"),
            industry=data.get("Industry"),
        )

    @staticmethod
    def _parse_opportunity(data: dict) -> SalesforceOpportunity:
        return SalesforceOpportunity(
            id=data.get("Id", ""),
            name=data.get("Name", ""),
            amount=float(data.get("Amount") or 0),
            stage=data.get("StageName", ""),
            close_date=data.get("CloseDate", ""),
            type=data.get("Type", ""),
            account_id=data.get("AccountId", ""),
        )

    @staticmethod
    def _parse_contact(data: dict) -> SalesforceContact:
        return SalesforceContact(
            id=data.get("Id", ""),
            name=data.get("Name", ""),
            email=data.get("Email"),
            role=data.get("Role__c"),
            account_id=data.get("AccountId", ""),
        )


# ---------------------------------------------------------------------------
# Evidence mapping functions
# ---------------------------------------------------------------------------


def opportunities_to_evidence(opportunities: list[SalesforceOpportunity]) -> list[dict]:
    """Map grant opportunities to ``evidence[]`` items for the Open Org profile.

    Only ``type='Grant'`` opportunities are included — donations and program
    opportunities are skipped. Each grant becomes an ``outcome_data`` evidence
    item with the amount and close date.
    """
    items: list[dict] = []
    idx = 0
    for opp in opportunities:
        if opp.type != "Grant":
            continue
        idx += 1
        outcomes = [
            {
                "metric": "grant_amount",
                "value": opp.amount,
                "currency": "GBP",
                "description": f"Grant of £{opp.amount:,.0f} closing {opp.close_date}",
            }
        ]
        items.append(
            {
                "evidence_id": f"sf-grant-{idx}",
                "title": opp.name,
                "evidence_type": "outcome_data",
                "date": opp.close_date,
                "url": None,
                "themes": [],
                "outcomes": outcomes,
            }
        )
    return items


def contacts_to_evidence(contacts: list[SalesforceContact]) -> list[dict]:
    """Map Salesforce contacts to ``evidence[]`` items.

    Contacts provide relationship evidence, mapped to ``evidence_type:
    'case_study'``. Each contact becomes an evidence item with their role.
    """
    items: list[dict] = []
    for i, c in enumerate(contacts):
        items.append(
            {
                "evidence_id": f"sf-contact-{i + 1}",
                "title": c.name,
                "evidence_type": "case_study",
                "date": _date.today().isoformat(),
                "url": None,
                "themes": [],
                "outcomes": [],
                "source": {
                    "system": "salesforce",
                    "contact_id": c.id,
                    "email": c.email,
                    "role": c.role,
                    "account_id": c.account_id,
                },
            }
        )
    return items