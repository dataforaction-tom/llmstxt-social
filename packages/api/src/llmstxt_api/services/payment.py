"""Payment verification and Stripe services."""

import stripe
from fastapi import HTTPException

from llmstxt_api.config import settings

# Configure Stripe
stripe.api_key = settings.stripe_secret_key


class PaymentError(Exception):
    """Payment verification error."""
    pass


async def verify_payment_intent(payment_intent_id: str, expected_amount: int = 900) -> dict:
    """
    Verify a payment intent with Stripe.

    Args:
        payment_intent_id: The Stripe payment intent ID to verify
        expected_amount: Expected amount in pence (default £9.00)

    Returns:
        dict with payment details including metadata

    Raises:
        PaymentError: If payment is invalid, not succeeded, or wrong amount
    """
    try:
        # Fetch payment intent from Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Verify payment status
        if intent.status != "succeeded":
            raise PaymentError(
                f"Payment not completed. Status: {intent.status}. "
                "Please complete payment before generating."
            )

        # Verify amount
        if intent.amount != expected_amount:
            raise PaymentError(
                f"Invalid payment amount. Expected {expected_amount}, got {intent.amount}"
            )

        # Verify currency
        if intent.currency.lower() != "gbp":
            raise PaymentError(
                f"Invalid currency. Expected GBP, got {intent.currency}"
            )

        return {
            "id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
            "metadata": dict(intent.metadata),
            "created": intent.created,
        }

    except stripe.InvalidRequestError as e:
        raise PaymentError(f"Invalid payment intent: {str(e)}")
    except stripe.StripeError as e:
        raise PaymentError(f"Stripe error: {str(e)}")


async def create_checkout_session(
    url: str,
    template: str,
    success_url: str,
    cancel_url: str,
    sector: str = "general",
    goal: str | None = None,
    customer_email: str | None = None,
) -> dict:
    """
    Create a Stripe Checkout Session for subscription.

    Args:
        url: The URL to monitor
        template: The template type (charity, funder, etc.)
        success_url: URL to redirect to on success
        cancel_url: URL to redirect to on cancel
        sector: Sub-sector within template
        goal: Primary goal for the organisation
        customer_email: Optional customer email

    Returns:
        dict with session_id and checkout_url
    """
    if not settings.stripe_monitoring_price_id:
        raise PaymentError("Subscription pricing not configured")

    try:
        metadata = {
            "url": url,
            "template": template,
            "sector": sector,
        }
        if goal:
            metadata["goal"] = goal

        session_params = {
            "mode": "subscription",
            "line_items": [{
                "price": settings.stripe_monitoring_price_id,
                "quantity": 1,
            }],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "subscription_data": {
                "metadata": metadata,
            },
        }

        if customer_email:
            session_params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        return {
            "session_id": session.id,
            "checkout_url": session.url,
        }

    except stripe.StripeError as e:
        raise PaymentError(f"Failed to create checkout session: {str(e)}")


async def cancel_subscription(stripe_subscription_id: str) -> dict:
    """
    Cancel a Stripe subscription.

    Args:
        stripe_subscription_id: The Stripe subscription ID

    Returns:
        dict with cancellation details
    """
    try:
        subscription = stripe.Subscription.delete(stripe_subscription_id)

        return {
            "id": subscription.id,
            "status": subscription.status,
            "canceled_at": subscription.canceled_at,
        }

    except stripe.InvalidRequestError as e:
        raise PaymentError(f"Invalid subscription: {str(e)}")
    except stripe.StripeError as e:
        raise PaymentError(f"Failed to cancel subscription: {str(e)}")


async def get_subscription_status(stripe_subscription_id: str) -> dict:
    """
    Get the status of a Stripe subscription.

    Args:
        stripe_subscription_id: The Stripe subscription ID

    Returns:
        dict with subscription details
    """
    try:
        subscription = stripe.Subscription.retrieve(stripe_subscription_id)

        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "canceled_at": subscription.canceled_at,
        }

    except stripe.InvalidRequestError as e:
        raise PaymentError(f"Invalid subscription: {str(e)}")
    except stripe.StripeError as e:
        raise PaymentError(f"Failed to get subscription: {str(e)}")
