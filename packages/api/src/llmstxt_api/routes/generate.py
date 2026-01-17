"""Generation API endpoints."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.models import GenerationJob, User
from llmstxt_api.schemas import (
    GenerateRequest,
    GeneratePaidRequest,
    JobResponse,
    TemplateOptionsResponse,
    SectorOptionSchema,
    GoalOptionSchema,
    DismissFindingsRequest,
    RecalculatedScoreResponse,
)
from llmstxt_api.tasks.generate import generate_free_task, generate_paid_task
from llmstxt_api.services.payment import verify_payment_intent, PaymentError
from llmstxt_api.routes.auth import get_current_user, require_auth
from llmstxt_core.templates import (
    get_sectors_for_template,
    get_goals_for_template,
    get_default_goal,
    DEFAULT_SECTOR,
)

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

    # Apply defaults for sector and goal
    sector = request.sector or DEFAULT_SECTOR
    goal = request.goal or get_default_goal(request.template)

    # Create job
    job = GenerationJob(
        id=uuid.uuid4(),
        url=str(request.url),
        template=request.template,
        sector=sector,
        goal=goal,
        tier="free",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Queue background task
    generate_free_task.delay(str(job.id), str(request.url), request.template, sector, goal)

    return JobResponse.model_validate(job)


@router.post("/generate/paid", response_model=JobResponse, status_code=202)
async def generate_paid(
    request: GeneratePaidRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """
    Generate llms.txt with full assessment (paid tier).

    - Requires valid Stripe payment intent
    - Includes enrichment data (Charity Commission, 360Giving)
    - Includes full quality assessment with AI analysis
    - Result valid for 30 days
    - Links to user account if authenticated (viewable in dashboard)
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

    # Apply defaults for sector and goal
    sector = request.sector or DEFAULT_SECTOR
    goal = request.goal or get_default_goal(request.template)

    # Link to user via payment metadata if not authenticated
    if not user:
        customer_email = payment_info.get("metadata", {}).get("customer_email")
        if customer_email:
            user_result = await db.execute(
                select(User).where(User.email == customer_email.lower())
            )
            user = user_result.scalar_one_or_none()
            if not user:
                user = User(email=customer_email.lower())
                db.add(user)
                await db.flush()

    # Create job - link to user if authenticated
    job = GenerationJob(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        url=str(request.url),
        template=request.template,
        sector=sector,
        goal=goal,
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
    generate_paid_task.delay(str(job.id), str(request.url), request.template, sector, goal)

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


@router.get("/assessments", response_model=list[JobResponse])
async def list_user_assessments(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """
    List paid assessments for the authenticated user.

    Returns completed paid-tier generation jobs that haven't expired.
    These are the one-off £9 assessments stored for 30 days.
    """
    now = datetime.utcnow()

    result = await db.execute(
        select(GenerationJob)
        .where(
            GenerationJob.user_id == user.id,
            GenerationJob.tier == "paid",
            GenerationJob.status == "completed",
            GenerationJob.expires_at > now,
        )
        .order_by(GenerationJob.created_at.desc())
    )
    jobs = result.scalars().all()

    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/templates/{template}/options", response_model=TemplateOptionsResponse)
async def get_template_options(template: str):
    """
    Get available sectors and goals for a template type.

    Returns the list of sectors and goals that can be selected
    when generating llms.txt for this template type.
    """
    valid_templates = ["charity", "funder", "public_sector", "startup"]
    if template not in valid_templates:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template type. Must be one of: {', '.join(valid_templates)}"
        )

    sectors = get_sectors_for_template(template)
    goals = get_goals_for_template(template)

    return TemplateOptionsResponse(
        template=template,
        sectors=[
            SectorOptionSchema(id=s["id"], label=s["label"], description=s["description"])
            for s in sectors
        ],
        goals=[
            GoalOptionSchema(id=g["id"], label=g["label"])
            for g in goals
        ],
        default_sector=DEFAULT_SECTOR,
        default_goal=get_default_goal(template),
    )


@router.post("/jobs/{job_id}/dismiss-findings", response_model=RecalculatedScoreResponse)
async def dismiss_findings(
    job_id: str,
    request: DismissFindingsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Dismiss findings as not relevant and recalculate assessment score.

    This allows users to mark specific findings as not applicable to their
    organisation. The score is recalculated without re-crawling or regenerating.
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

    # Check if job has assessment data
    if not job.assessment_json:
        raise HTTPException(status_code=400, detail="Job has no assessment data to modify")

    # Get current assessment
    assessment = job.assessment_json
    findings = assessment.get("findings", [])

    # Validate indices
    for idx in request.dismissed_indices:
        if idx < 0 or idx >= len(findings):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid finding index: {idx}. Must be between 0 and {len(findings) - 1}"
            )

    # Merge with existing dismissed findings
    existing_dismissed = set(job.dismissed_findings or [])
    new_dismissed = existing_dismissed.union(set(request.dismissed_indices))
    job.dismissed_findings = list(new_dismissed)

    # Calculate remaining findings (not dismissed)
    remaining_findings = [
        f for i, f in enumerate(findings)
        if i not in new_dismissed
    ]

    # Recalculate quality score based on remaining findings
    # Quality score is based on severity of remaining issues
    severity_weights = {"critical": 25, "major": 15, "minor": 5, "info": 0}
    total_deductions = sum(
        severity_weights.get(f.get("severity", "info"), 0)
        for f in remaining_findings
    )
    new_quality_score = max(0, 100 - total_deductions)

    # Completeness score stays the same (based on structure, not findings)
    completeness_score = assessment.get("completeness_score", 50)

    # Recalculate overall score (weighted average)
    new_overall_score = int((completeness_score * 0.4) + (new_quality_score * 0.6))

    # Determine new grade
    if new_overall_score >= 90:
        new_grade = "A"
    elif new_overall_score >= 80:
        new_grade = "B"
    elif new_overall_score >= 70:
        new_grade = "C"
    elif new_overall_score >= 60:
        new_grade = "D"
    else:
        new_grade = "F"

    # Update assessment_json with recalculated scores
    assessment["overall_score"] = new_overall_score
    assessment["quality_score"] = new_quality_score
    assessment["grade"] = new_grade
    job.assessment_json = assessment

    await db.commit()

    return RecalculatedScoreResponse(
        overall_score=new_overall_score,
        completeness_score=completeness_score,
        quality_score=new_quality_score,
        grade=new_grade,
        dismissed_count=len(new_dismissed),
        remaining_findings=remaining_findings,
    )
