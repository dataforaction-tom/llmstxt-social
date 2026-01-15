"""Payment API endpoints (Stripe integration)."""

import uuid
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from llmstxt_api.config import settings
from llmstxt_api.database import get_db
from llmstxt_api.models import GenerationJob, Subscription
from llmstxt_api.schemas import CreatePaymentIntentRequest, CreatePaymentIntentResponse
from llmstxt_api.tasks.generate import generate_paid_task

router = APIRouter()
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.stripe_secret_key


@router.post("/create-intent", response_model=CreatePaymentIntentResponse)
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """
    Create a Stripe payment intent for one-time payment.

    Returns client_secret for frontend to complete payment.
    """
    try:
        # Calculate amount (could vary by template in future)
        amount = 900  # £9.00 in pence for one-time assessment

        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="gbp",
            metadata={
                "url": str(request.url),
                "template": request.template,
                "tier": "paid",
            },
            automatic_payment_methods={"enabled": True},
        )

        return CreatePaymentIntentResponse(
            client_secret=intent.client_secret,
            amount=amount,
            currency="gbp",
        )

    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.

    Processes payment confirmations and triggers generation jobs.
    Also handles subscription lifecycle events.
    """
    payload = await request.body()

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )

    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle event types
    if event.type == "payment_intent.succeeded":
        await handle_payment_intent_succeeded(event.data.object, db)

    elif event.type == "payment_intent.payment_failed":
        payment_intent = event.data.object
        logger.warning(f"Payment failed: {payment_intent.id}")

    elif event.type == "checkout.session.completed":
        await handle_checkout_session_completed(event.data.object, db)

    elif event.type == "customer.subscription.updated":
        await handle_subscription_updated(event.data.object, db)

    elif event.type == "customer.subscription.deleted":
        await handle_subscription_deleted(event.data.object, db)

    elif event.type == "invoice.payment_failed":
        await handle_invoice_payment_failed(event.data.object, db)

    return {"status": "success"}


async def handle_payment_intent_succeeded(payment_intent, db: AsyncSession):
    """Handle successful one-time payment."""
    payment_intent_id = payment_intent.id
    metadata = payment_intent.metadata

    logger.info(f"Payment succeeded: {payment_intent_id}")

    # Check if job already exists (created via generate/paid endpoint)
    existing = await db.execute(
        select(GenerationJob).where(
            GenerationJob.payment_intent_id == payment_intent_id
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Job already exists for payment {payment_intent_id}")
        return

    # Create job from webhook if metadata contains url and template
    url = metadata.get("url")
    template = metadata.get("template")

    if not url or not template:
        logger.warning(f"Payment {payment_intent_id} missing url/template metadata")
        return

    job = GenerationJob(
        id=uuid.uuid4(),
        url=url,
        template=template,
        tier="paid",
        status="pending",
        payment_intent_id=payment_intent_id,
        amount_paid=payment_intent.amount,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )

    db.add(job)
    await db.commit()

    # Queue background task
    generate_paid_task.delay(str(job.id), url, template)
    logger.info(f"Created job {job.id} from webhook for payment {payment_intent_id}")


async def handle_checkout_session_completed(session, db: AsyncSession):
    """Handle successful subscription checkout."""
    if session.mode != "subscription":
        return

    subscription_id = session.subscription
    metadata = session.metadata or {}

    logger.info(f"Checkout completed for subscription: {subscription_id}")

    # Check if subscription already exists
    existing = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription_id
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Subscription {subscription_id} already exists")
        return

    url = metadata.get("url")
    template = metadata.get("template", "charity")

    if not url:
        logger.warning(f"Checkout session {session.id} missing url metadata")
        return

    # Get customer email from session
    customer_email = session.customer_details.email if session.customer_details else None

    # Create subscription record
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),  # Anonymous user for now
        url=url,
        template=template,
        frequency="monthly",
        active=True,
        stripe_subscription_id=subscription_id,
    )

    db.add(subscription)
    await db.commit()

    logger.info(f"Created subscription {subscription.id} for {url}")


async def handle_subscription_updated(stripe_subscription, db: AsyncSession):
    """Handle subscription status updates."""
    subscription_id = stripe_subscription.id
    status = stripe_subscription.status

    logger.info(f"Subscription {subscription_id} updated to status: {status}")

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(f"Subscription {subscription_id} not found in database")
        return

    # Update subscription based on status
    if status in ("active", "trialing"):
        subscription.active = True
        subscription.cancelled_at = None
    elif status in ("past_due", "unpaid"):
        subscription.active = True  # Keep active but payment is failing
    elif status in ("canceled", "incomplete_expired"):
        subscription.active = False
        subscription.cancelled_at = datetime.utcnow()

    await db.commit()
    logger.info(f"Updated subscription {subscription.id} active={subscription.active}")


async def handle_subscription_deleted(stripe_subscription, db: AsyncSession):
    """Handle subscription cancellation."""
    subscription_id = stripe_subscription.id

    logger.info(f"Subscription {subscription_id} deleted")

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(f"Subscription {subscription_id} not found in database")
        return

    subscription.active = False
    subscription.cancelled_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Cancelled subscription {subscription.id}")


async def handle_invoice_payment_failed(invoice, db: AsyncSession):
    """Handle failed subscription renewal payment."""
    subscription_id = invoice.subscription
    customer_email = invoice.customer_email

    logger.warning(
        f"Invoice payment failed for subscription {subscription_id}, "
        f"customer: {customer_email}"
    )

    # Could send notification email here if needed
    # For now, just log - subscription status update will handle deactivation
