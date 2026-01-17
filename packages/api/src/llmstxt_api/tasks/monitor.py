"""Monitoring background tasks for subscription-based llms.txt updates."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from llmstxt_api.config import settings
from llmstxt_api.models import Subscription, MonitoringHistory, User
from llmstxt_api.tasks.celery import celery_app

logger = logging.getLogger(__name__)


def get_async_session():
    """Create a new async engine and session for each task."""
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def run_monitoring_check(subscription_id: str) -> dict:
    """
    Run a monitoring check for a subscription.

    Regenerates llms.txt and compares with previous version.
    """
    from llmstxt_api.services.generation import generate_with_enrichment, assess_llmstxt

    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as db:
        # Get subscription
        result = await db.execute(
            select(Subscription).where(Subscription.id == uuid.UUID(subscription_id))
        )
        subscription = result.scalar_one_or_none()

        if not subscription or not subscription.active:
            logger.warning(f"Subscription {subscription_id} not found or inactive")
            return {"status": "skipped", "reason": "inactive"}

        try:
            # Generate new llms.txt with enrichment
            logger.info(f"Generating llms.txt for subscription {subscription_id}")
            new_content, enrichment_data = await generate_with_enrichment(
                url=subscription.url,
                template=subscription.template,
                sector=subscription.sector or "general",
                goal=subscription.goal,
            )

            # Assess the generated content
            assessment = await assess_llmstxt(
                llmstxt_content=new_content,
                template=subscription.template,
                website_url=subscription.url,
                enrichment_data=enrichment_data,
                sector=subscription.sector or "general",
                goal=subscription.goal,
            )

            # Get previous monitoring entry
            prev_result = await db.execute(
                select(MonitoringHistory)
                .where(MonitoringHistory.subscription_id == subscription.id)
                .order_by(MonitoringHistory.checked_at.desc())
                .limit(1)
            )
            previous = prev_result.scalar_one_or_none()

            # Check for changes
            changed = False
            if previous and previous.llmstxt_content:
                # Simple content comparison - could be made smarter
                changed = previous.llmstxt_content.strip() != new_content.strip()
            else:
                # First check - consider it a "change" to establish baseline
                changed = True

            # Create monitoring history entry
            history = MonitoringHistory(
                id=uuid.uuid4(),
                subscription_id=subscription.id,
                checked_at=datetime.utcnow(),
                changed=changed,
                llmstxt_content=new_content,
                assessment_json=assessment,
                notification_sent=False,
            )

            db.add(history)

            # Update subscription
            subscription.last_check = datetime.utcnow()
            if changed:
                subscription.last_change_detected = datetime.utcnow()

            await db.commit()

            logger.info(
                f"Monitoring check complete for {subscription_id}: changed={changed}"
            )

            # Send notification if changed
            if changed and previous:  # Don't notify on first check
                await send_change_notification(subscription, new_content, db)
                history.notification_sent = True
                await db.commit()

            return {
                "status": "completed",
                "changed": changed,
                "subscription_id": subscription_id,
            }

        except Exception as e:
            logger.error(f"Error monitoring subscription {subscription_id}: {e}")
            return {"status": "failed", "error": str(e)}


async def send_change_notification(
    subscription: Subscription,
    new_content: str,
    db: AsyncSession,
):
    """Send email notification about llms.txt changes."""
    import resend

    resend.api_key = settings.resend_api_key

    # Look up user email from subscription
    user_result = await db.execute(
        select(User).where(User.id == subscription.user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        logger.warning(f"No user found for subscription {subscription.id}")
        return

    try:
        # Format URL for display
        try:
            from urllib.parse import urlparse
            domain = urlparse(subscription.url).netloc
        except Exception:
            domain = subscription.url

        resend.Emails.send({
            "from": settings.from_email,
            "to": [user.email],
            "subject": f"llms.txt updated for {domain}",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #6366f1;">llms.txt Changes Detected</h2>
                    <p>We've detected changes in the llms.txt file for <strong>{domain}</strong>.</p>
                    <p style="color: #666;">
                        Your monitored website's content has changed since our last check.
                        We've automatically regenerated your llms.txt file with the updated information.
                    </p>
                    <div style="background: #f3f4f6; border-radius: 8px; padding: 16px; margin: 24px 0;">
                        <p style="margin: 0; font-size: 14px;"><strong>URL:</strong> {subscription.url}</p>
                        <p style="margin: 8px 0 0 0; font-size: 14px;"><strong>Template:</strong> {subscription.template}</p>
                        <p style="margin: 8px 0 0 0; font-size: 14px;"><strong>Checked:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
                    </div>
                    <a href="{settings.frontend_url}/dashboard"
                       style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 8px; margin: 16px 0;">
                        View in Dashboard
                    </a>
                    <p style="color: #666; font-size: 14px; margin-top: 32px;">
                        You're receiving this because you have an active monitoring subscription.
                        You can manage your subscriptions in your <a href="{settings.frontend_url}/dashboard" style="color: #6366f1;">dashboard</a>.
                    </p>
                </div>
            """,
        })
        logger.info(f"Sent change notification to {user.email} for subscription {subscription.id}")
    except Exception as e:
        logger.error(f"Failed to send notification email: {e}")


@celery_app.task(name="monitor.check_subscription")
def check_subscription_task(subscription_id: str) -> dict:
    """
    Celery task to check a single subscription.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_monitoring_check(subscription_id))
    finally:
        loop.close()


@celery_app.task(name="monitor.check_due_subscriptions")
def check_due_subscriptions_task() -> dict:
    """
    Check all subscriptions that are due for monitoring.

    Called by Celery beat scheduler.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check_due_subscriptions())
    finally:
        loop.close()


async def _check_due_subscriptions() -> dict:
    """Find and queue subscriptions due for monitoring."""
    AsyncSessionLocal = get_async_session()

    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()

        # Find active subscriptions that need checking
        result = await db.execute(
            select(Subscription).where(Subscription.active == True)
        )
        subscriptions = result.scalars().all()

        queued = 0
        for sub in subscriptions:
            if _is_check_due(sub, now):
                check_subscription_task.delay(str(sub.id))
                queued += 1
                logger.info(f"Queued monitoring check for subscription {sub.id}")

        logger.info(f"Queued {queued} subscription checks")
        return {"queued": queued, "total_active": len(subscriptions)}


def _is_check_due(subscription: Subscription, now: datetime) -> bool:
    """Determine if a subscription is due for a monitoring check."""
    if not subscription.last_check:
        # Never checked before
        return True

    if subscription.frequency == "weekly":
        threshold = timedelta(days=7)
    elif subscription.frequency == "monthly":
        threshold = timedelta(days=30)
    else:
        threshold = timedelta(days=7)  # Default to weekly

    return (now - subscription.last_check) >= threshold
