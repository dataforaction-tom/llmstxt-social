"""Celery tasks for generation jobs."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from llmstxt_api.config import settings
from llmstxt_api.models import GenerationJob
from llmstxt_api.services.generation import (
    generate_llmstxt_from_url,
    generate_with_enrichment,
    assess_llmstxt,
)
from llmstxt_api.tasks.celery import celery_app

# Create async engine for Celery tasks
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def update_job_status(job_id: uuid.UUID, status: str, **kwargs):
    """Update job status in database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(GenerationJob).where(GenerationJob.id == job_id))
        job = result.scalar_one_or_none()

        if job:
            job.status = status
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

    async def run():
        try:
            # Update status to processing
            await update_job_status(job_id, "processing")

            # Generate llms.txt
            llmstxt_content = await generate_llmstxt_from_url(url, template)

            # Update job with result
            await update_job_status(
                job_id,
                "completed",
                llmstxt_content=llmstxt_content,
                completed_at=datetime.utcnow(),
            )

            print(f"✓ Free generation completed for job {job_id}")

        except Exception as e:
            # Update job with error
            await update_job_status(
                job_id,
                "failed",
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

    job_id = uuid.UUID(job_id_str)

    async def run():
        try:
            # Update status to processing
            await update_job_status(job_id, "processing")

            # Generate with enrichment
            llmstxt_content, enrichment_data = await generate_with_enrichment(url, template)

            # Run assessment
            assessment = await assess_llmstxt(
                llmstxt_content=llmstxt_content,
                template=template,
                website_url=url,
                enrichment_data=enrichment_data,
            )

            # Update job with results
            await update_job_status(
                job_id,
                "completed",
                llmstxt_content=llmstxt_content,
                assessment_json=assessment,
                completed_at=datetime.utcnow(),
            )

            print(f"✓ Paid generation completed for job {job_id}")

        except Exception as e:
            # Update job with error
            await update_job_status(
                job_id,
                "failed",
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            print(f"✗ Paid generation failed for job {job_id}: {e}")
            raise

    # Run async function
    asyncio.run(run())
