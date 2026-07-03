"""Hypercerts integration — on-chain impact-claim tokens.

Hypercerts are ERC-1155 semi-fungible tokens on Ethereum (Optimism mainnet)
representing a discrete piece of work and impact. This module builds the
claim data from a verified evidence item, provides a mockable mint function,
and fetches hypercerts from the subgraph.

The on-chain interaction is abstracted behind injectable callables so tests
never touch a real blockchain.

Pipeline:
    CRM outcome data → evidence[] item → validate → build_claim → mint_claim
    → token ID stored in evidence item → public on profile + Hypercerts registry

Guardrails:
    - Only ``evidence_type: "outcome_data"`` with populated ``outcomes[]``
      can be minted. No aspirations, no plans.
    - The ``contributors`` field includes the CRM system identity as a
      provenance chain.
    - Minting is irreversible — the MCP tool requires explicit admin confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

# Default chain: Optimism mainnet (chain ID 10)
_DEFAULT_CHAIN_ID = 10
_HYPERCERTS_EXPLORER_URL = "https://explorer.hypercerts.org"


@dataclass
class HypercertClaim:
    """A hypercert claim ready for on-chain minting."""

    work_scope: str
    impact_scope: str
    contributors: list[str]
    timeframe_start: int  # YYYYMMDD
    timeframe_end: int  # YYYYMMDD
    units: int
    evidence_ref: str
    org_id: str
    token_id: str | None = None
    transaction_hash: str | None = None
    chain_id: int | None = None


# Type aliases for injectable functions
MintFn = Callable[[HypercertClaim], Awaitable[dict]]
QueryFn = Callable[[str], Awaitable[list[dict]]]


# ---------------------------------------------------------------------------
# validate_evidence_for_minting
# ---------------------------------------------------------------------------


def validate_evidence_for_minting(evidence: dict) -> dict[str, Any]:
    """Check whether an evidence item is eligible for hypercert minting.

    Rules:
    - ``evidence_type`` must be ``"outcome_data"`` (no aspirations/plans)
    - ``outcomes`` array must exist and be non-empty
    """
    if evidence.get("evidence_type") != "outcome_data":
        return {
            "valid": False,
            "reason": "Only evidence_type 'outcome_data' can be minted as a hypercert",
        }

    outcomes = evidence.get("outcomes")
    if not outcomes or not isinstance(outcomes, list) or len(outcomes) == 0:
        return {
            "valid": False,
            "reason": "outcome_data evidence must have a non-empty outcomes[] array",
        }

    return {"valid": True}


# ---------------------------------------------------------------------------
# build_claim
# ---------------------------------------------------------------------------


def build_claim(evidence: dict, *, org_id: str) -> HypercertClaim:
    """Construct a HypercertClaim from a verified evidence item.

    Derives:
    - ``work_scope`` from the evidence title + themes
    - ``impact_scope`` from the outcomes descriptions
    - ``timeframe`` from the evidence date (year start → year end)
    - ``units`` from the outcome values (e.g. total beneficiaries)
    - ``contributors`` from the org_id + CRM source provenance
    """
    title = evidence.get("title") or "Untitled impact"
    themes = evidence.get("themes") or []

    # Work scope: title + themes
    work_parts = [title]
    if themes:
        work_parts.append(f"Themes: {', '.join(themes)}")
    work_scope = " | ".join(work_parts)

    # Impact scope: outcomes descriptions
    outcomes = evidence.get("outcomes") or []
    impact_parts = []
    total_units = 0
    for o in outcomes:
        desc = o.get("description") or ""
        metric = o.get("metric") or ""
        value = o.get("value")
        n = o.get("n")
        if desc:
            impact_parts.append(desc)
        elif metric and value is not None:
            impact_parts.append(f"{metric}: {value}")
        # Sum up n (beneficiaries) or value as units
        if n and isinstance(n, (int, float)):
            total_units += int(n)
        elif value is not None and isinstance(value, (int, float)):
            total_units += int(value)

    impact_scope = "; ".join(impact_parts) if impact_parts else "Impact measured"
    units = max(total_units, 1)  # At least 1 unit

    # Timeframe from evidence date (YYYY-MM-DD → YYYY0101 → YYYY1231)
    date_str = evidence.get("date") or "2024-01-01"
    year = int(date_str[:4]) if len(date_str) >= 4 else 2024
    timeframe_start = year * 10000 + 101  # YYYY0101
    timeframe_end = year * 10000 + 1231  # YYYY1231

    # Contributors: org_id + CRM provenance
    contributors = [org_id]
    source = evidence.get("source")
    if isinstance(source, dict):
        crm = source.get("crm")
        profile_id = source.get("profile_id")
        if crm and profile_id:
            contributors.append(f"{crm}:{profile_id}")

    return HypercertClaim(
        work_scope=work_scope,
        impact_scope=impact_scope,
        contributors=contributors,
        timeframe_start=timeframe_start,
        timeframe_end=timeframe_end,
        units=units,
        evidence_ref=evidence.get("evidence_id") or "",
        org_id=org_id,
    )


# ---------------------------------------------------------------------------
# mint_claim
# ---------------------------------------------------------------------------


async def mint_claim(
    claim: HypercertClaim,
    *,
    mint_fn: MintFn,
) -> dict[str, Any]:
    """Submit a hypercert mint transaction via the injected ``mint_fn``.

    The ``mint_fn`` handles the actual on-chain interaction (wallet signing,
    gas estimation, transaction submission). It returns a dict with
    ``token_id``, ``transaction_hash``, and ``chain_id``.

    Returns a result dict with ``success``, ``token_id``, ``transaction_hash``,
    and ``chain_id`` on success, or ``success=False`` + ``error`` on failure.
    """
    try:
        result = await mint_fn(claim)
        return {
            "success": True,
            "token_id": str(result.get("token_id", "")),
            "transaction_hash": str(result.get("transaction_hash", "")),
            "chain_id": int(result.get("chain_id", _DEFAULT_CHAIN_ID)),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# fetch_hypercerts_for_org
# ---------------------------------------------------------------------------


async def fetch_hypercerts_for_org(
    org_id: str,
    *,
    query_fn: QueryFn,
) -> list[dict[str, Any]]:
    """Fetch all hypercerts attributed to an org from the subgraph.

    The ``query_fn`` is an async callable that takes the org_id and returns
    a list of hypercert dicts. Errors degrade to an empty list.
    """
    try:
        return await query_fn(org_id)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# hypercert_to_evidence
# ---------------------------------------------------------------------------


def hypercert_to_evidence(hypercert: dict[str, Any]) -> dict[str, Any]:
    """Map an on-chain hypercert back to an evidence[] item.

    This is used when displaying hypercerts on the public profile — the
    on-chain token is the verified evidence, with the impact scope as the
    measured outcome.
    """
    token_id = str(hypercert.get("token_id", ""))
    work_scope = hypercert.get("work_scope") or "Untitled impact"
    impact_scope = hypercert.get("impact_scope") or ""
    chain_id = hypercert.get("chain_id", _DEFAULT_CHAIN_ID)

    url = f"{_HYPERCERTS_EXPLORER_URL}/token/{token_id}" if token_id else None

    outcomes = []
    if impact_scope:
        outcomes.append({
            "metric": "impact_scope",
            "description": impact_scope,
        })

    return {
        "evidence_id": f"hypercert-{token_id}" if token_id else "hypercert-unknown",
        "title": work_scope,
        "evidence_type": "outcome_data",
        "date": None,
        "url": url,
        "themes": [],
        "outcomes": outcomes,
        "hypercert": {
            "token_id": token_id,
            "claim_hash": hypercert.get("claim_hash"),
            "chain_id": int(chain_id) if chain_id else _DEFAULT_CHAIN_ID,
            "transaction_hash": hypercert.get("transaction_hash"),
            "units": hypercert.get("units"),
        },
    }


__all__ = [
    "HypercertClaim",
    "build_claim",
    "fetch_hypercerts_for_org",
    "hypercert_to_evidence",
    "mint_claim",
    "validate_evidence_for_minting",
]