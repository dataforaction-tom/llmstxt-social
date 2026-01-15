"""Celery tasks for generation jobs."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from llmstxt_api.config import settings
from llmstxt_api.models import GenerationJob
from llmstxt_api.tasks.celery import celery_app

# Import core functions for step-by-step progress
from llmstxt_core import crawl_site, extract_content, generate_llmstxt
from llmstxt_core.analyzer import analyze_organisation


def get_async_session():
    """Create a new async engine and session for each task."""
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def update_job_progress(session_maker, job_id: uuid.UUID, **kwargs):
    """Update job progress in database."""
    async with session_maker() as session:
        result = await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        job = result.scalar_one_or_none()

        if job:
            for key, value in kwargs.items():
                setattr(job, key, value)
            await session.commit()


@celery_app.task(name="generate_free_task", bind=True)
def generate_free_task(self, job_id_str: str, url: str, template: str):
    """
    Background task for free tier generation.

    Args:
        job_id_str: Job ID as string
        url: Website URL
        template: Template type
    """
    import asyncio

    job_id = uuid.UUID(job_id_str)
    max_pages = settings.max_crawl_pages

    async def run():
        # Create fresh session maker for this event loop
        session_maker = get_async_session()

        try:
            # Stage 1: Crawling
            await update_job_progress(
                session_maker,
                job_id,
                status="processing",
                progress_stage="crawling",
                progress_detail=f"Discovering pages on {url}",
                total_pages=max_pages,
                pages_crawled=0,
            )

            crawl_result = await crawl_site(url, max_pages=max_pages)
            pages_found = len(crawl_result.pages)

            # Stage 2: Extracting content
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="extracting",
                progress_detail=f"Extracting content from {pages_found} pages",
                pages_crawled=pages_found,
                total_pages=pages_found,
            )

            pages = [extract_content(page) for page in crawl_result.pages]

            # Stage 3: Analyzing with AI
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="analyzing",
                progress_detail="Analyzing content with Claude AI",
            )

            analysis = await analyze_organisation(pages, template, api_key=settings.anthropic_api_key)

            # Stage 4: Generating llms.txt
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="generating",
                progress_detail="Generating llms.txt file",
            )

            llmstxt_content = generate_llmstxt(analysis, pages, template)

            # Complete
            await update_job_progress(
                session_maker,
                job_id,
                status="completed",
                progress_stage="completed",
                progress_detail="Generation complete",
                llmstxt_content=llmstxt_content,
                completed_at=datetime.utcnow(),
            )

            print(f"✓ Free generation completed for job {job_id}")

        except Exception as e:
            # Update job with error
            await update_job_progress(
                session_maker,
                job_id,
                status="failed",
                progress_stage="failed",
                progress_detail=str(e)[:200],
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            print(f"✗ Free generation failed for job {job_id}: {e}")
            raise

    # Run async function
    asyncio.run(run())


@celery_app.task(name="generate_paid_task", bind=True)
def generate_paid_task(self, job_id_str: str, url: str, template: str):
    """
    Background task for paid tier generation.

    Includes enrichment and full assessment.

    Args:
        job_id_str: Job ID as string
        url: Website URL
        template: Template type
    """
    import asyncio
    from anthropic import Anthropic
    from llmstxt_core.assessor import LLMSTxtAssessor
    from llmstxt_core.enrichers.charity_commission import fetch_charity_data, find_charity_number

    job_id = uuid.UUID(job_id_str)
    max_pages = settings.max_crawl_pages

    async def run():
        # Create fresh session maker for this event loop
        session_maker = get_async_session()

        try:
            # Stage 1: Crawling
            await update_job_progress(
                session_maker,
                job_id,
                status="processing",
                progress_stage="crawling",
                progress_detail=f"Discovering pages on {url}",
                total_pages=max_pages,
                pages_crawled=0,
            )

            crawl_result = await crawl_site(url, max_pages=max_pages)
            pages_found = len(crawl_result.pages)

            # Stage 2: Extracting content
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="extracting",
                progress_detail=f"Extracting content from {pages_found} pages",
                pages_crawled=pages_found,
                total_pages=pages_found,
            )

            pages = [extract_content(page) for page in crawl_result.pages]

            # Stage 3: Enrichment (for charities)
            enrichment_data = None
            if template == "charity" and settings.charity_commission_api_key:
                await update_job_progress(
                    session_maker,
                    job_id,
                    progress_stage="enriching",
                    progress_detail="Fetching Charity Commission data",
                )
                charity_number = find_charity_number(pages)
                if charity_number:
                    enrichment_data = await fetch_charity_data(
                        charity_number, api_key=settings.charity_commission_api_key
                    )

            # Stage 4: Analyzing with AI
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="analyzing",
                progress_detail="Analyzing content with Claude AI",
            )

            analysis = await analyze_organisation(pages, template, api_key=settings.anthropic_api_key)

            # Stage 5: Generating llms.txt
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="generating",
                progress_detail="Generating llms.txt file",
            )

            llmstxt_content = generate_llmstxt(analysis, pages, template)

            # Stage 6: Assessment
            await update_job_progress(
                session_maker,
                job_id,
                progress_stage="assessing",
                progress_detail="Running quality assessment",
            )

            client = Anthropic(api_key=settings.anthropic_api_key)
            assessor = LLMSTxtAssessor(template, client)
            assessment_result = await assessor.assess(
                llmstxt_content=llmstxt_content,
                website_url=url,
                enrichment_data=enrichment_data,
            )

            # Compute grade from overall score
            score = assessment_result.overall_score
            if score >= 90:
                grade = "A"
            elif score >= 80:
                grade = "B"
            elif score >= 70:
                grade = "C"
            elif score >= 60:
                grade = "D"
            else:
                grade = "F"

            # Convert assessment to dict
            assessment = {
                "overall_score": assessment_result.overall_score,
                "completeness_score": assessment_result.completeness_score,
                "quality_score": assessment_result.quality_score,
                "grade": grade,
                "findings": [
                    {
                        "category": f.category.value,
                        "severity": f.severity.value,
                        "message": f.message,
                        "suggestion": f.suggestion,
                    }
                    for f in assessment_result.findings
                ],
                "recommendations": assessment_result.recommendations,
            }

            # Complete
            await update_job_progress(
                session_maker,
                job_id,
                status="completed",
                progress_stage="completed",
                progress_detail="Generation and assessment complete",
                llmstxt_content=llmstxt_content,
                assessment_json=assessment,
                completed_at=datetime.utcnow(),
            )

            print(f"✓ Paid generation completed for job {job_id}")

        except Exception as e:
            # Update job with error
            await update_job_progress(
                session_maker,
                job_id,
                status="failed",
                progress_stage="failed",
                progress_detail=str(e)[:200],
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            print(f"✗ Paid generation failed for job {job_id}: {e}")
            raise

    # Run async function
    asyncio.run(run())
