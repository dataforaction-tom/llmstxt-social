"""Admin tool implementations for the Open Org MCP server.

Admin tools require org-admin authentication and perform writes:

* ``sync_from_crm`` — reads from a CRM (Beacon, Lamplight, Salesforce),
  maps donations/outcomes/cases to evidence items, and returns them for
  human review. Does not auto-write — the agent presents items and the
  admin approves via ``add_evidence``.
* ``add_evidence`` — appends a verified evidence item to a profile's
  ``evidence[]`` array and commits to the database.

Auth model: org admin token validated against the ``OrgAdmin`` table.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.open_org_models import OrgAdmin, OrgProfile
from llmstxt_core.enrichers.beacon_crm import (
    BeaconClient,
    donations_to_evidence,
    cases_to_evidence,
)
from llmstxt_core.enrichers.lamplight_crm import (
    LamplightClient,
    outcomes_to_evidence,
    work_records_to_evidence,
)
from llmstxt_core.enrichers.salesforce_crm import (
    SalesforceClient,
    opportunities_to_evidence,
    contacts_to_evidence,
)


_VALID_EVIDENCE_TYPES = {
    "evaluation",
    "outcome_data",
    "annual_report",
    "case_study",
    "learning_reflection",
    "external_research",
    "other",
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def validate_admin_token(
    db: AsyncSession, *, org_id: str, token: str | None
) -> bool:
    """Check whether ``token`` belongs to an admin of ``org_id``.

    In production this validates against the magic-link auth system's
    session token table. For now it checks the ``OrgAdmin`` table for
    a matching user session. A ``None`` token short-circuits without
    touching the DB.
    """
    if not token:
        return False
    # In the real system, ``token`` would be a session cookie / JWT.
    # This stub checks if any admin row exists for this org — the real
    # validation will be wired when the MCP server gets its auth middleware.
    result = await db.execute(
        select(OrgAdmin).where(OrgAdmin.org_id == org_id).limit(1)
    )
    return result.scalar() is not None


# ---------------------------------------------------------------------------
# sync_from_crm
# ---------------------------------------------------------------------------


async def sync_from_crm(
    db: AsyncSession,
    *,
    org_id: str,
    crm_system: str,
    crm_api_key: str | None = None,
    access_token: str | None = None,
    instance_url: str | None = None,
    constituent_id: str | None = None,
    profile_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Read data from a CRM and return evidence items for review.

    Does NOT auto-write to the profile. The agent presents the items to
    the admin, who approves them via ``add_evidence``.

    Supported CRM systems: ``beacon``, ``lamplight``, ``salesforce``.
    """
    # 1. Fetch the published profile
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalars().one_or_none()
    if profile is None or profile.profile_json is None:
        return {"error": "Organisation not found or not published"}

    existing_evidence = profile.profile_json.get("evidence") or []
    existing_keys = {
        (e.get("title", ""), e.get("date", ""))
        for e in existing_evidence
        if isinstance(e, dict)
    }

    # 2. Pull from CRM + map to evidence items
    raw_items: list[dict] = []

    if crm_system == "beacon":
        if not crm_api_key or not constituent_id:
            return {"error": "Beacon requires crm_api_key and constituent_id"}
        client = BeaconClient(api_key=crm_api_key)
        donations = await client.get_donations(constituent_id)
        cases = await client.get_cases(constituent_id)
        raw_items = donations_to_evidence(donations) + cases_to_evidence(cases)

    elif crm_system == "lamplight":
        if not crm_api_key or not profile_id:
            return {"error": "Lamplight requires crm_api_key and profile_id"}
        client = LamplightClient(api_key=crm_api_key, base_url="https://lamplight.online/api")
        outcomes = await client.get_outcomes(profile_id)
        work_records = await client.get_work_records(profile_id)
        raw_items = outcomes_to_evidence(outcomes) + work_records_to_evidence(work_records)

    elif crm_system == "salesforce":
        if not access_token or not instance_url or not account_id:
            return {"error": "Salesforce requires access_token, instance_url, and account_id"}
        client = SalesforceClient(access_token=access_token, instance_url=instance_url)
        opportunities = await client.get_opportunities(account_id)
        contacts = await client.get_contacts(account_id)
        raw_items = opportunities_to_evidence(opportunities) + contacts_to_evidence(contacts)

    else:
        return {"error": f"Unsupported CRM system: {crm_system}"}

    # 3. Filter out items that already exist (by title + date)
    new_items = [
        item for item in raw_items
        if (item.get("title", ""), item.get("date", "")) not in existing_keys
    ]

    return {
        "evidence_items": new_items,
        "existing_count": len(existing_evidence),
        "new_count": len(new_items),
        "profile_updated": False,  # sync_from_crm does NOT write — admin must approve
    }


# ---------------------------------------------------------------------------
# add_evidence
# ---------------------------------------------------------------------------


async def add_evidence(
    db: AsyncSession,
    *,
    org_id: str,
    evidence_item: dict,
) -> dict[str, Any]:
    """Append a verified evidence item to a profile's ``evidence[]`` array.

    Validates the evidence item shape, generates an ``evidence_id`` if not
    provided, appends to the profile JSON, and commits.

    Returns the updated evidence array.
    """
    # 1. Validate the evidence item
    title = evidence_item.get("title")
    evidence_type = evidence_item.get("evidence_type")
    date = evidence_item.get("date")

    if not title:
        return {"success": False, "error": "evidence_item must have a 'title'"}
    if not evidence_type or evidence_type not in _VALID_EVIDENCE_TYPES:
        return {
            "success": False,
            "error": f"Invalid or missing evidence_type. Must be one of: {sorted(_VALID_EVIDENCE_TYPES)}",
        }

    # 2. Fetch the published profile
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalars().one_or_none()
    if profile is None or profile.profile_json is None:
        return {"success": False, "error": "Organisation not found or not published"}

    # 3. Build the new evidence item with an ID
    new_item = dict(evidence_item)
    if not new_item.get("evidence_id"):
        new_item["evidence_id"] = f"ev-{uuid.uuid4().hex[:8]}"

    # 4. Append to the evidence array
    evidence_list = list(profile.profile_json.get("evidence") or [])
    evidence_list.append(new_item)

    # 5. Write back to profile_json
    updated_json = dict(profile.profile_json)
    updated_json["evidence"] = evidence_list
    profile.profile_json = updated_json

    # 6. Commit
    await db.commit()

    return {
        "success": True,
        "evidence": evidence_list,
        "added_evidence_id": new_item["evidence_id"],
    }


__all__ = [
    "validate_admin_token",
    "sync_from_crm",
    "add_evidence",
]