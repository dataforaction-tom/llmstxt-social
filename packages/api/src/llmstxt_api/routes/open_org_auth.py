"""Authentication primitives for Open Org admin routes.

Builds on the existing magic-link auth in ``routes/auth.py``: organisations
sign in via magic link (same flow as everywhere else), then their User is
checked against the ``org_admins`` table for the org they're trying to edit.

The :func:`require_org_admin` dependency is the gate for all edit routes;
:func:`grant_org_admin` is called by the profile generator (Step 5) when a
profile is first claimed by an email owner.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.models import MagicLinkToken, User
from llmstxt_api.open_org_models import OrgAdmin
from llmstxt_api.routes.auth import require_auth


VALID_ROLES = frozenset({"owner", "editor"})

# Claim links carry a longer TTL than login links — owners read claim emails
# on their own schedule. 24h is generous without being permanent.
CLAIM_LINK_TTL_HOURS = 24


async def require_org_admin(
    org_id: str,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> OrgAdmin:
    """Dependency: assert the current user is an admin of ``org_id``.

    Returns the :class:`OrgAdmin` row so routes that care about role
    (e.g. only owners can add other admins) can branch on it.
    """
    result = await db.execute(
        select(OrgAdmin).where(
            OrgAdmin.user_id == user.id,
            OrgAdmin.org_id == org_id,
        )
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"not an admin of organisation {org_id}",
        )
    return admin


async def grant_org_admin(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    org_id: str,
    role: str = "editor",
) -> OrgAdmin:
    """Create an :class:`OrgAdmin` row for the given (user, org) pair.

    Caller is responsible for committing the session.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role {role!r}; expected one of {sorted(VALID_ROLES)}")
    row = OrgAdmin(user_id=user_id, org_id=org_id, role=role)
    db.add(row)
    return row


async def create_claim_token(
    db: AsyncSession,
    *,
    email: str,
    org_id: str,
    ttl_hours: int = CLAIM_LINK_TTL_HOURS,
) -> tuple[str, MagicLinkToken]:
    """Create a ``MagicLinkToken`` bound to ``org_id`` and return the raw token.

    Caller commits the session. The raw token is what goes in the email URL;
    only the row's ``token`` column holds the same value, so leaking the raw
    string equals leaking the cookie. Keep TTL short-ish.
    """
    raw = secrets.token_urlsafe(32)
    row = MagicLinkToken(
        email=email.strip().lower(),
        token=raw,
        org_id=org_id,
        expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(row)
    return raw, row


__all__ = [
    "CLAIM_LINK_TTL_HOURS",
    "create_claim_token",
    "grant_org_admin",
    "require_org_admin",
    "VALID_ROLES",
]
