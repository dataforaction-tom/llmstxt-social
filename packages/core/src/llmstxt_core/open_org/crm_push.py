"""CRM Pattern B — one-way push from an Open Org profile into a CRM.

The push direction: take an Open Org profile (optionally carrying an
``ideas`` array) and write relevant data INTO a CRM via its REST API.

This is the inverse of Pattern A (read-only enrichment). Pattern B
*writes* to the CRM, so HTTP errors propagate — silent failure on a
write is worse than a loud one.

Mapping functions are pure (no I/O) so they can be unit-tested in
isolation. :func:`push_profile_to_crm` is the async orchestrator that
selects the CRM by name, maps the profile, and performs the writes via
the existing CRM client classes (:class:`BeaconClient`,
:class:`LamplightClient`, :class:`SalesforceClient`).
"""

from __future__ import annotations

from typing import Any, Callable

from llmstxt_core.enrichers.beacon_crm import BeaconClient
from llmstxt_core.enrichers.lamplight_crm import LamplightClient
from llmstxt_core.enrichers.salesforce_crm import SalesforceClient


__all__ = [
    "ideas_to_beacon_campaigns",
    "ideas_to_salesforce_opportunities",
    "profile_to_beacon_constituent",
    "profile_to_lamplight_profile",
    "profile_to_salesforce_account",
    "push_profile_to_crm",
]


# ---------------------------------------------------------------------------
# Field mapping functions (pure)
# ---------------------------------------------------------------------------


def profile_to_beacon_constituent(profile_json: dict) -> dict:
    """Map an Open Org profile to Beacon CRM constituent fields.

    Maps:
    * ``identity.name`` → ``name``
    * ``identity.registration.charity_commission_ew`` →
      ``custom_fields.charity_number`` (when present)
    * ``mission.themes`` → ``tags``
    * ``mission.summary`` → ``description``
    """
    identity = profile_json.get("identity") or {}
    mission = profile_json.get("mission") or {}
    registration = identity.get("registration") or {}

    custom_fields: dict[str, Any] = {}
    charity_no = registration.get("charity_commission_ew")
    if charity_no:
        custom_fields["charity_number"] = charity_no

    return {
        "name": identity.get("name") or "",
        "tags": list(mission.get("themes") or []),
        "description": mission.get("summary") or "",
        "custom_fields": custom_fields,
    }


def profile_to_lamplight_profile(profile_json: dict) -> dict:
    """Map an Open Org profile to Lamplight profile fields.

    Maps:
    * ``identity.name`` → ``name``
    * ``mission.themes`` → ``tags`` (service tags)
    * ``ideas[]`` → ``work_records[]`` (one work record per idea;
      ``type`` is the idea id, ``notes`` is the idea summary)
    """
    identity = profile_json.get("identity") or {}
    mission = profile_json.get("mission") or {}
    ideas = profile_json.get("ideas") or []

    work_records = [
        {
            "type": idea.get("id") or "",
            "notes": idea.get("summary") or "",
        }
        for idea in ideas
    ]

    return {
        "name": identity.get("name") or "",
        "tags": list(mission.get("themes") or []),
        "work_records": work_records,
    }


def profile_to_salesforce_account(profile_json: dict) -> dict:
    """Map an Open Org profile to a Salesforce Account.

    Maps:
    * ``identity.name`` → ``Name``
    * ``identity.registration.charity_commission_ew`` → ``Charity_Number__c``
    * ``identity.website`` → ``Website``
    * ``mission.themes`` → ``Topics__c`` (semicolon-joined)
    """
    identity = profile_json.get("identity") or {}
    mission = profile_json.get("mission") or {}
    registration = identity.get("registration") or {}

    account: dict[str, Any] = {
        "Name": identity.get("name") or "",
    }

    charity_no = registration.get("charity_commission_ew")
    if charity_no:
        account["Charity_Number__c"] = charity_no

    website = identity.get("website")
    if website:
        account["Website"] = website

    themes = list(mission.get("themes") or [])
    if themes:
        account["Topics__c"] = ";".join(themes)

    return account


def ideas_to_beacon_campaigns(ideas: list[dict]) -> list[dict]:
    """Map Open Org ideas to Beacon campaign records.

    Each idea becomes a campaign with ``name`` (idea id), ``description``
    (idea summary), and ``status`` (idea status).
    """
    return [
        {
            "name": idea.get("id") or "",
            "description": idea.get("summary") or "",
            "status": idea.get("status") or "",
        }
        for idea in ideas
    ]


# Maps Open Org idea status → Salesforce Opportunity StageName.
_SF_STAGE_MAP = {
    "seed": "Prospecting",
    "developing": "Developing",
    "shaped": "Qualification",
    "delivered": "Closed Won",
    "archived": "Closed Lost",
}


def ideas_to_salesforce_opportunities(ideas: list[dict]) -> list[dict]:
    """Map Open Org ideas to Salesforce Opportunity records.

    Each idea becomes an Opportunity with ``Name`` (idea id), ``Amount``
    (the upper bound of ``indicative_cost``, or 0 if absent), and
    ``StageName`` (mapped from the idea status).
    """
    opportunities: list[dict] = []
    for idea in ideas:
        cost = idea.get("indicative_cost") or {}
        amount = cost.get("upper") if isinstance(cost, dict) else None
        opportunities.append(
            {
                "Name": idea.get("id") or "",
                "Amount": amount if isinstance(amount, (int, float)) else 0,
                "StageName": _SF_STAGE_MAP.get(
                    idea.get("status") or "", "Prospecting"
                ),
            }
        )
    return opportunities


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def push_profile_to_crm(
    profile_json: dict,
    crm_system: str,
    **credentials: Any,
) -> dict:
    """Push an Open Org profile into a CRM.

    Selects the CRM by ``crm_system`` (one of ``"beacon"``,
    ``"lamplight"``, ``"salesforce"``), maps the profile + ideas to the
    CRM's schema, and writes via the CRM client's create methods.

    All HTTP is injectable through the ``http_client_factory`` credential
    (passed through to the CRM client constructor). HTTP errors propagate
    as :class:`httpx.HTTPStatusError` — writes should fail loudly.

    Returns a dict summarising what was created, including the
    ``system`` and the IDs of the created records.
    """
    if crm_system == "beacon":
        return await _push_to_beacon(profile_json, **credentials)
    if crm_system == "lamplight":
        return await _push_to_lamplight(profile_json, **credentials)
    if crm_system == "salesforce":
        return await _push_to_salesforce(profile_json, **credentials)
    raise ValueError(f"unsupported crm_system: {crm_system!r}")


async def _push_to_beacon(profile_json: dict, **credentials: Any) -> dict:
    factory: Callable[[], Any] | None = credentials.pop("http_client_factory", None)
    client = BeaconClient(
        api_key=credentials.pop("api_key"),
        base_url=credentials.pop("base_url", "https://api.beaconcrm.org/api/v1"),
        http_client_factory=factory,
    )

    constituent_payload = profile_to_beacon_constituent(profile_json)
    constituent = await client.create_constituent(constituent_payload)
    constituent_id = constituent.get("id") or ""

    campaigns = ideas_to_beacon_campaigns(profile_json.get("ideas") or [])
    campaigns_created = 0
    for campaign in campaigns:
        await client.create_campaign(constituent_id, campaign)
        campaigns_created += 1

    return {
        "system": "beacon",
        "constituent_id": constituent_id,
        "campaigns_created": campaigns_created,
    }


async def _push_to_lamplight(profile_json: dict, **credentials: Any) -> dict:
    factory: Callable[[], Any] | None = credentials.pop("http_client_factory", None)
    client = LamplightClient(
        api_key=credentials.pop("api_key"),
        base_url=credentials.pop("base_url", ""),
        http_client_factory=factory,
    )

    lamplight_payload = profile_to_lamplight_profile(profile_json)
    # Work records are created separately, so strip them from the profile payload.
    work_records = lamplight_payload.pop("work_records", [])
    created = await client.create_profile(lamplight_payload)
    profile_id = created.get("id") or ""

    work_records_created = 0
    for wr in work_records:
        await client.create_work_record(profile_id, wr)
        work_records_created += 1

    return {
        "system": "lamplight",
        "profile_id": profile_id,
        "work_records_created": work_records_created,
    }


async def _push_to_salesforce(profile_json: dict, **credentials: Any) -> dict:
    factory: Callable[[], Any] | None = credentials.pop("http_client_factory", None)
    client = SalesforceClient(
        access_token=credentials.pop("access_token"),
        instance_url=credentials.pop("instance_url"),
        http_client_factory=factory,
    )

    account_payload = profile_to_salesforce_account(profile_json)
    account = await client.create_account(account_payload)
    account_id = account.get("id") or ""

    opportunities = ideas_to_salesforce_opportunities(
        profile_json.get("ideas") or []
    )
    opportunities_created = 0
    for opp in opportunities:
        await client.create_opportunity(account_id, opp)
        opportunities_created += 1

    return {
        "system": "salesforce",
        "account_id": account_id,
        "opportunities_created": opportunities_created,
    }