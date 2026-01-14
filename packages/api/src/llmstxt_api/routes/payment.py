"""Payment API endpoints (Stripe integration)."""

from fastapi import APIRouter, Header, HTTPException, Request
import stripe

from llmstxt_api.config import settings
from llmstxt_api.schemas import CreatePaymentIntentRequest, CreatePaymentIntentResponse

router = APIRouter()

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
        amount = 2900  # £29.00 in pence

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
):
    """
    Handle Stripe webhook events.

    Processes payment confirmations and triggers generation jobs.
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
        payment_intent = event.data.object

        # Payment succeeded - job creation is handled in generate_paid endpoint
        # This webhook confirms the payment was successful
        print(f"✓ Payment succeeded: {payment_intent.id}")

    elif event.type == "payment_intent.payment_failed":
        payment_intent = event.data.object
        print(f"✗ Payment failed: {payment_intent.id}")

    # Add more event handlers as needed

    return {"status": "success"}
