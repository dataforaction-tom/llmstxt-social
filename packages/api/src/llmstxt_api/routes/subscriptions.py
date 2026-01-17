"""Subscription API endpoints for monitoring service."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.database import get_db
from llmstxt_api.models import Subscription, MonitoringHistory, User
from llmstxt_api.schemas import (
    SubscriptionCreate,
    SubscriptionResponse,
    CheckoutSessionResponse,
    MonitoringHistoryResponse,
)
from llmstxt_api.services.payment import (
    create_checkout_session,
    cancel_subscription as stripe_cancel_subscription,
    get_subscription_status,
    PaymentError,
)
from llmstxt_api.routes.auth import get_current_user, require_auth
from llmstxt_core.templates import DEFAULT_SECTOR, get_default_goal

router = APIRouter()


@router.post("/subscriptions", response_model=CheckoutSessionResponse, status_code=201)
async def create_subscription(
    request: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """
    Create a new monitoring subscription.

    Initiates Stripe Checkout session for subscription payment.
    Returns checkout URL for frontend to redirect user to.
    """
    # Apply defaults for sector and goal
    sector = request.sector or DEFAULT_SECTOR
    goal = request.goal or get_default_goal(request.template)

    try:
        customer_email = request.email or (user.email if user else None)
        checkout = await create_checkout_session(
            url=str(request.url),
            template=request.template,
            sector=sector,
            goal=goal,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=customer_email,
            user_email=user.email if user else None,
        )

        return CheckoutSessionResponse(
            session_id=checkout["session_id"],
            checkout_url=checkout["checkout_url"],
        )

    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
    active_only: bool = True,
):
    """
    List subscriptions for the authenticated user.
    """
    query = select(Subscription).where(Subscription.user_id == user.id)
    if active_only:
        query = query.where(Subscription.active == True)

    result = await db.execute(query.order_by(Subscription.created_at.desc()))
    subscriptions = result.scalars().all()

    return [SubscriptionResponse.model_validate(s) for s in subscriptions]


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """
    Get subscription details.
    """
    try:
        sub_uuid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription ID format")

    result = await db.execute(
        select(Subscription).where(
            Subscription.id == sub_uuid,
            Subscription.user_id == user.id,
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return SubscriptionResponse.model_validate(subscription)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """
    Cancel a subscription.

    Cancels the Stripe subscription and marks local record as cancelled.
    """
    try:
        sub_uuid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription ID format")

    result = await db.execute(
        select(Subscription).where(
            Subscription.id == sub_uuid,
            Subscription.user_id == user.id,
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if not subscription.active:
        raise HTTPException(status_code=400, detail="Subscription already cancelled")

    # Cancel in Stripe
    if subscription.stripe_subscription_id:
        try:
            await stripe_cancel_subscription(subscription.stripe_subscription_id)
        except PaymentError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update local record
    subscription.active = False
    subscription.cancelled_at = datetime.utcnow()
    await db.commit()
    await db.refresh(subscription)

    return SubscriptionResponse.model_validate(subscription)


@router.get(
    "/subscriptions/{subscription_id}/history",
    response_model=list[MonitoringHistoryResponse],
)
async def get_subscription_history(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth),
    limit: int = 20,
):
    """
    Get monitoring history for a subscription.

    Returns recent monitoring checks and whether changes were detected.
    """
    try:
        sub_uuid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription ID format")

    # Verify subscription exists and belongs to user
    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.id == sub_uuid,
            Subscription.user_id == user.id,
        )
    )
    if not sub_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get history
    result = await db.execute(
        select(MonitoringHistory)
        .where(MonitoringHistory.subscription_id == sub_uuid)
        .order_by(MonitoringHistory.checked_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()

    return [MonitoringHistoryResponse.model_validate(h) for h in history]


@router.get("/subscriptions/{subscription_id}/status")
async def check_subscription_status(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check subscription status with Stripe.

    Returns both local and Stripe status for debugging/admin.
    """
    try:
        sub_uuid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription ID format")

    result = await db.execute(
        select(Subscription).where(Subscription.id == sub_uuid)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    response = {
        "local": {
            "id": str(subscription.id),
            "active": subscription.active,
            "cancelled_at": subscription.cancelled_at,
        }
    }

    if subscription.stripe_subscription_id:
        try:
            stripe_status = await get_subscription_status(
                subscription.stripe_subscription_id
            )
            response["stripe"] = stripe_status
        except PaymentError as e:
            response["stripe_error"] = str(e)

    return response
