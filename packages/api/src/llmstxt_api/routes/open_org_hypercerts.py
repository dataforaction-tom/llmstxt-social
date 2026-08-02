"""Hypercerts REST API routes for Open Org.

Three endpoints:

* ``POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert``
  Admin-only (``require_org_admin``). Mints a Hypercert on-chain from a
  verified evidence item, writes the token reference back into the
  profile's ``evidence[]`` array, and regenerates ``markdown_source`` so
  the editor doesn't wipe it on the next save.

* ``GET /open-org/{org_id}/hypercerts``
  Public. Lists all minted hypercerts (evidence items with a ``hypercert``
  field) for a published org.

* ``GET /open-org/{org_id}/hypercerts/{token_id}``
  Public. Returns a single hypercert's detail (the evidence item that
  carries the matching ``hypercert.token_id``).

The minting pipeline mirrors :func:`openorg_mcp.admin_tools.mint_hypercert`:
fetch published profile → find evidence → validate → build claim →
submit via injectable ``mint_fn`` → write back → regenerate markdown → commit.

The ``mint_fn`` is a custodial-wallet concern (not yet built). For the API
route it defaults to a placeholder that reads from the ``HYPERCERTS_MINT_FUNCTION``
env var, falling back to a mock minter returning a fake token id. Tests inject
their own ``mint_fn``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgAdmin, OrgProfile
from llmstxt_api.routes.open_org_auth import require_org_admin
from llmstxt_core.open_org.converter import json_to_markdown
from llmstxt_core.open_org.hypercerts import (
    HypercertClaim,
    build_claim,
    mint_claim,
    validate_evidence_for_minting,
)

# ---------------------------------------------------------------------------
# Routers
#
# The admin mint route mounts under /api/open-org (same prefix as the admin
# edit router). The two public read routes mount under /open-org (same prefix
# as the public serving router). We use a single module-level router for the
# admin endpoint and a separate one for the public endpoints, then merge them
# via a parent router so ``main.py`` only needs a single include_router call.
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/api/open-org", tags=["open-org-hypercerts"])
public_router = APIRouter(prefix="/open-org", tags=["open-org-hypercerts"])

router = APIRouter()
router.include_router(admin_router)
router.include_router(public_router)


# 5-minute browser/CDN cache — same as the public serving routes.
_CACHE_CONTROL = "public, max-age=300"


# ---------------------------------------------------------------------------
# Placeholder mint function
# ---------------------------------------------------------------------------


async def _placeholder_mint_fn(claim: HypercertClaim) -> dict[str, Any]:
    """Default mint function used when no real wallet minter is configured.

    Reads the ``HYPERCERTS_MINT_FUNCTION`` env var. If unset, returns a fake
    token so the API contract is testable end-to-end without a wallet. This
    is a custodial-wallet concern — the real implementation will swap this out.
    """
    configured = os.environ.get("HYPERCERTS_MINT_FUNCTION")
    if configured:
        # A real implementation would import/call the configured callable.
        # For now, just return a deterministic fake based on the configured name.
        return {
            "token_id": f"placeholder-{configured}",
            "transaction_hash": f"0x{configured[:8].ljust(8, '0')}",
            "chain_id": 10,
        }
    return {
        "token_id": "placeholder-000001",
        "transaction_hash": "0x0000000000000000000000000000000000000000",
        "chain_id": 10,
    }


# ---------------------------------------------------------------------------
# POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert (admin)
# ---------------------------------------------------------------------------


async def mint_hypercert(
    org_id: str,
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    admin: OrgAdmin = Depends(require_org_admin),
    mint_fn: Callable[[HypercertClaim], Awaitable[dict]] | None = None,
) -> dict[str, Any]:
    """Mint a Hypercert from a verified evidence item.

    Pipeline (mirrors the MCP admin tool):
    1. Fetch the published profile (404 if missing or has no content)
    2. Find the evidence item by ``evidence_id`` (404 if not found)
    3. Validate with ``validate_evidence_for_minting()`` (400 if invalid)
    4. Build the on-chain claim via ``build_claim()``
    5. Submit via ``mint_fn`` (502 if the mint fails)
    6. Update the evidence item with the hypercert reference
    7. Regenerate ``markdown_source`` from the updated profile_json
    8. Commit

    Returns ``{"success": true, "token_id": ..., "transaction_hash": ..., "chain_id": ...}``.
    """
    # 1. Fetch the published profile
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.profile_json is None:
        raise HTTPException(status_code=404, detail="profile not found or has no content")

    # 2. Find the evidence item
    evidence_list = list(profile.profile_json.get("evidence") or [])
    evidence_item: dict[str, Any] | None = None
    for ev in evidence_list:
        if isinstance(ev, dict) and ev.get("evidence_id") == evidence_id:
            evidence_item = ev
            break

    if evidence_item is None:
        raise HTTPException(
            status_code=404,
            detail=f"evidence item '{evidence_id}' not found in profile",
        )

    # 3. Validate for minting
    validation = validate_evidence_for_minting(evidence_item)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["reason"],
        )

    # 4. Build the claim
    claim = build_claim(evidence_item, org_id=org_id)

    # 5. Submit the mint
    fn = mint_fn if mint_fn is not None else _placeholder_mint_fn
    mint_result = await mint_claim(claim, mint_fn=fn)
    if not mint_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=mint_result.get("error", "mint failed"),
        )

    # 6. Update the evidence item with the hypercert reference
    for i, ev in enumerate(evidence_list):
        if isinstance(ev, dict) and ev.get("evidence_id") == evidence_id:
            evidence_list[i] = {
                **ev,
                "hypercert": {
                    "token_id": mint_result["token_id"],
                    "chain_id": mint_result["chain_id"],
                    "transaction_hash": mint_result["transaction_hash"],
                },
            }
            break

    # Write back
    updated_json = dict(profile.profile_json)
    updated_json["evidence"] = evidence_list
    profile.profile_json = updated_json

    # 7. Regenerate markdown_source so the editor doesn't wipe the hypercert
    # reference on the next save (same fix applied to the MCP tool).
    profile.markdown_source = json_to_markdown(updated_json, kind="profile")

    # 8. Commit
    await db.commit()

    return {
        "success": True,
        "token_id": mint_result["token_id"],
        "transaction_hash": mint_result["transaction_hash"],
        "chain_id": mint_result["chain_id"],
    }


# Register the admin route on the admin router.
admin_router.add_api_route(
    "/{org_id}/evidence/{evidence_id}/mint-hypercert",
    mint_hypercert,
    methods=["POST"],
)


# ---------------------------------------------------------------------------
# GET /open-org/{org_id}/hypercerts (public)
# ---------------------------------------------------------------------------


async def list_hypercerts(org_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """List all minted hypercerts for a published org.

    Extracts every evidence item that carries a ``hypercert`` field and
    returns a JSON array of summary objects. 404 if the profile isn't
    published (no existence leak).
    """
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.profile_json is None:
        raise HTTPException(status_code=404, detail="profile not found")

    summaries = []
    for ev in profile.profile_json.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        hc = ev.get("hypercert")
        if not isinstance(hc, dict):
            continue
        summaries.append(_hypercert_summary(ev))

    return Response(
        content=_json_list_body(summaries),
        media_type="application/json",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


public_router.add_api_route("/{org_id}/hypercerts", list_hypercerts, methods=["GET"])


# ---------------------------------------------------------------------------
# GET /open-org/{org_id}/hypercerts/{token_id} (public)
# ---------------------------------------------------------------------------


async def get_hypercert(
    org_id: str, token_id: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Return a single hypercert's detail (the evidence item carrying it).

    Matches ``hypercert.token_id`` as a string comparison (the URL path param
    is always a string; the stored value may be int or str). 404 if the
    profile isn't published or no evidence item carries that token_id.
    """
    result = await db.execute(
        select(OrgProfile).where(
            OrgProfile.org_id == org_id,
            OrgProfile.published.is_(True),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.profile_json is None:
        raise HTTPException(status_code=404, detail="profile not found")

    for ev in profile.profile_json.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        hc = ev.get("hypercert")
        if not isinstance(hc, dict):
            continue
        if str(hc.get("token_id", "")) == token_id:
            return Response(
                content=_json_body(ev),
                media_type="application/json",
                headers={"Cache-Control": _CACHE_CONTROL},
            )

    raise HTTPException(status_code=404, detail="hypercert not found")


public_router.add_api_route(
    "/{org_id}/hypercerts/{token_id}", get_hypercert, methods=["GET"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hypercert_summary(ev: dict[str, Any]) -> dict[str, Any]:
    """Build a summary object for the hypercerts list endpoint."""
    hc = ev.get("hypercert") or {}
    summary: dict[str, Any] = {
        "evidence_id": ev.get("evidence_id"),
        "title": ev.get("title"),
        "token_id": hc.get("token_id"),
        "chain_id": hc.get("chain_id"),
        "transaction_hash": hc.get("transaction_hash"),
    }
    # Include themes if present (useful for the registry UI).
    themes = ev.get("themes")
    if themes:
        summary["themes"] = themes
    return summary


def _json_body(payload: dict | None) -> bytes:
    """Serialize a dict to bytes (empty → ``{}``)."""
    return json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")


def _json_list_body(items: list[dict]) -> bytes:
    return json.dumps(items, ensure_ascii=False).encode("utf-8")


__all__ = ["router", "admin_router", "public_router"]