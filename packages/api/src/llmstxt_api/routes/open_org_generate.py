"""POST /api/open-org/generate — kick off Open Org profile generation.

Unauthenticated by design (per spec section 1): any visitor can submit a
charity number. The Celery task runs the generator, populates the row, and
emails a magic-link claim to ``owner_email`` — that's where ownership gets
established.

A conflict is returned for an existing ``ready`` profile to prevent overwriting
a published profile someone else already owns. ``failed`` rows are retryable
(the most common cause is a transient CC API hiccup).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.open_org_models import OrgProfile
from llmstxt_api.tasks.open_org_generate import generate_open_org_profile_task


router = APIRouter(prefix="/api/open-org", tags=["open-org"])


# Loose email check — Resend handles real deliverability. Pulling in
# ``pydantic[email]`` (which needs ``email-validator``) for a single use
# isn't worth the dep.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class GenerateRequest(BaseModel):
    charity_number: str = Field(
        ...,
        pattern=r"^[0-9]{6,8}$",
        description="UK Charity Commission registration number (6-8 digits).",
    )
    owner_email: str = Field(
        ...,
        pattern=_EMAIL_PATTERN,
        description="Email to send the claim/magic-link to when generation completes.",
    )


class GenerateResponse(BaseModel):
    org_id: str
    profile_id: str
    generation_status: str
    task_id: str | None = None


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_profile(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    org_id = f"GB-CHC-{request.charity_number}"

    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    existing = result.scalar_one_or_none()

    if existing is not None and existing.generation_status != "failed":
        # A pending/generating/ready profile is owned (or about to be) by the
        # current claimant flow; refuse to overwrite. The owner can edit via
        # the admin routes after claiming.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "profile_already_exists",
                "org_id": org_id,
                "generation_status": existing.generation_status,
            },
        )

    if existing is None:
        profile = OrgProfile(org_id=org_id, generation_status="pending")
        db.add(profile)
    else:
        # Retry after a failed run — clear the error and re-queue.
        profile = existing
        profile.generation_status = "pending"
        profile.generation_error = None

    await db.commit()
    await db.refresh(profile)

    handle = generate_open_org_profile_task.delay(
        profile_id=str(profile.id),
        charity_number=request.charity_number,
        owner_email=request.owner_email,
    )

    return GenerateResponse(
        org_id=org_id,
        profile_id=str(profile.id),
        generation_status="pending",
        task_id=getattr(handle, "id", None),
    )


__all__ = ["GenerateRequest", "GenerateResponse", "generate_profile", "router"]
