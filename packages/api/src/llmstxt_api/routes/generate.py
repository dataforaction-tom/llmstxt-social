"""Generation API endpoints."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.models import GenerationJob
from llmstxt_api.schemas import GenerateRequest, GeneratePaidRequest, JobResponse
from llmstxt_api.tasks.generate import generate_free_task, generate_paid_task
from llmstxt_api.services.payment import verify_payment_intent, PaymentError

router = APIRouter()


@router.post("/generate/free", response_model=JobResponse, status_code=202)
async def generate_free(
    request: GenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate llms.txt (free tier).

    - Rate limited to 10 requests per day per IP
    - No enrichment data
    - No quality assessment
    - Result expires after 7 days
    """
    # TODO: Check rate limit based on IP
    client_ip = http_request.client.host

    # Create job
    job = GenerationJob(
        id=uuid.uuid4(),
        url=str(request.url),
        template=request.template,
        tier="free",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Queue background task
    generate_free_task.delay(str(job.id), str(request.url), request.template)

    return JobResponse.model_validate(job)


@router.post("/generate/paid", response_model=JobResponse, status_code=202)
async def generate_paid(
    request: GeneratePaidRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate llms.txt with full assessment (paid tier).

    - Requires valid Stripe payment intent
    - Includes enrichment data (Charity Commission, 360Giving)
    - Includes full quality assessment with AI analysis
    - Result valid for 30 days
    """
    # Check for duplicate job with same payment_intent_id
    existing_job = await db.execute(
        select(GenerationJob).where(
            GenerationJob.payment_intent_id == request.payment_intent_id
        )
    )
    existing = existing_job.scalar_one_or_none()

    if existing:
        # Return existing job instead of creating duplicate
        return JobResponse.model_validate(existing)

    # Verify payment intent with Stripe
    try:
        payment_info = await verify_payment_intent(request.payment_intent_id)
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create job
    job = GenerationJob(
        id=uuid.uuid4(),
        url=str(request.url),
        template=request.template,
        tier="paid",
        status="pending",
        payment_intent_id=request.payment_intent_id,
        amount_paid=payment_info["amount"],
        expires_at=datetime.utcnow() + timedelta(days=30),
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Queue background task
    generate_paid_task.delay(str(job.id), str(request.url), request.template)

    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get job status and results.

    Returns the current status of a generation job. When completed,
    includes the generated llms.txt content and assessment (for paid tier).
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    # Query job
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_uuid))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if expired
    if job.expires_at and job.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Job has expired")

    return JobResponse.model_validate(job)
