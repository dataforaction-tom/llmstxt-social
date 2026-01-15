# Stripe Setup Guide

Complete guide to setting up Stripe for one-time payments (£9 assessments) and subscriptions (£9/month monitoring).

## Table of Contents

1. [Create Stripe Account](#step-1-create-stripe-account)
2. [Get API Keys](#step-2-get-your-api-keys)
3. [Create Products](#step-3-create-products)
4. [Set Up Webhooks](#step-4-set-up-webhooks)
5. [Configure Environment Variables](#step-5-configure-environment-variables)
6. [Restart Services](#step-6-restart-services)
7. [Test Payments](#step-7-test-payments)
8. [Going to Production](#going-to-production)
9. [Troubleshooting](#troubleshooting)

---

## Step 1: Create Stripe Account

1. Go to [stripe.com](https://stripe.com) and click "Start now"
2. Complete the registration process
3. For development, stay in **Test mode** (toggle in top-right of dashboard)

---

## Step 2: Get Your API Keys

1. Go to **Developers → API keys** in the Stripe Dashboard
2. You'll see two keys:

| Key Type | Starts With | Used For |
|----------|-------------|----------|
| Publishable key | `pk_test_` | Frontend (safe to expose) |
| Secret key | `sk_test_` | Backend (keep secret!) |

3. Click "Reveal test key" to see your secret key
4. Copy both keys - you'll need them for your `.env` file

---

## Step 3: Create Products

### 3a. One-Time Assessment Product (£9)

1. Go to **Products → Add product**
2. Fill in:
   - **Name**: `llms.txt Assessment`
   - **Description**: `Full llms.txt generation with quality assessment and enrichment data`
3. Under **Price information**:
   - **Pricing model**: One time
   - **Amount**: `29.00`
   - **Currency**: GBP
4. Click **Save product**

> **Note**: The one-time payment uses Payment Intents (already configured in the code), so you don't need to copy this price ID.

### 3b. Subscription Product (£9/month)

1. Go to **Products → Add product**
2. Fill in:
   - **Name**: `llms.txt Monitoring`
   - **Description**: `Automated weekly monitoring and regeneration of your llms.txt file`
3. Under **Price information**:
   - **Pricing model**: Recurring
   - **Amount**: `9.00`
   - **Currency**: GBP
   - **Billing period**: Monthly
4. Click **Save product**
5. **Important**: After saving, click on the product, find the Price section, and copy the **Price ID** (starts with `price_`)

---

## Step 4: Set Up Webhooks

Webhooks notify your application when payment events occur (successful payments, subscription changes, etc.).

### For Production/Deployed Environment

1. Go to **Developers → Webhooks**
2. Click **Add endpoint**
3. Configure:
   - **Endpoint URL**: `https://your-domain.com/api/payment/webhook`
   - **Description**: `llmstxt payment events`
4. Under **Select events to listen to**, click **Select events** and check:

   **Payment Intent events:**
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`

   **Checkout events:**
   - `checkout.session.completed`

   **Subscription events:**
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`

   **Invoice events:**
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`

5. Click **Add endpoint**
6. On the webhook details page, click **Reveal** under Signing secret
7. Copy the **Signing secret** (starts with `whsec_`)

### For Local Development

Use the Stripe CLI to forward webhooks to your local server:

1. **Install Stripe CLI**:

   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe

   # Windows (with scoop)
   scoop install stripe

   # Windows (with chocolatey)
   choco install stripe-cli

   # Or download from: https://stripe.com/docs/stripe-cli
   ```

2. **Login to Stripe**:

   ```bash
   stripe login
   ```

   This opens a browser to authenticate.

3. **Forward webhooks to localhost**:

   ```bash
   stripe listen --forward-to localhost:8000/api/payment/webhook
   ```

4. The CLI will output a webhook signing secret like:

   ```
   Ready! Your webhook signing secret is whsec_xxxxxxxxxxxxx
   ```

   Copy this for your local `.env` file.

5. **Keep this terminal running** while testing payments locally.

---

## Step 5: Configure Environment Variables

Create or update your `.env` file in the project root:

```bash
# Stripe API Keys (from Step 2)
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxx

# Subscription Price ID (from Step 3b)
STRIPE_MONITORING_PRICE_ID=price_xxxxxxxxxxxxxxxxxxxxxxxx

# Frontend publishable key
VITE_STRIPE_PUBLIC_KEY=pk_test_xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Step 6: Restart Services

```bash
# Stop existing containers
docker-compose down

# Rebuild and start with new env vars
docker-compose up -d --build

# Check logs
docker-compose logs -f api
```

---

## Step 7: Test Payments

### Test Cards

Use these test card numbers:

| Scenario | Card Number | CVC | Expiry |
|----------|-------------|-----|--------|
| Success | `4242 4242 4242 4242` | Any 3 digits | Any future date |
| Declined | `4000 0000 0000 0002` | Any 3 digits | Any future date |
| Requires authentication | `4000 0025 0000 3155` | Any 3 digits | Any future date |
| Insufficient funds | `4000 0000 0000 9995` | Any 3 digits | Any future date |

### Test One-Time Payment (£9)

1. Go to `http://localhost:3000/generate`
2. Enter a URL and select "Paid - £9"
3. Click "Generate (Proceed to Payment)"
4. Enter test card `4242 4242 4242 4242`
5. Use any future expiry date and any CVC
6. Complete payment
7. Verify job is created and processing starts

### Test Subscription (£9/month)

1. Go to `http://localhost:3000/subscribe`
2. Enter a URL to monitor
3. Click "Continue to Payment - £9/month"
4. You'll be redirected to Stripe Checkout
5. Enter test card `4242 4242 4242 4242`
6. Complete payment
7. You'll be redirected to `/dashboard?subscription=success`
8. Verify subscription appears in the dashboard

### Verify Webhooks Are Working

If you have the Stripe CLI running, you'll see output like:

```
2024-01-15 10:30:45   --> payment_intent.succeeded [evt_xxx]
2024-01-15 10:30:45  <--  [200] POST http://localhost:8000/api/payment/webhook
```

Check your API logs for confirmation:

```bash
docker-compose logs -f api | grep -i "payment\|subscription"
```

### Test Subscription Cancellation

1. Go to `http://localhost:3000/dashboard`
2. Find your active subscription
3. Click "Cancel Subscription"
4. Confirm the cancellation
5. Verify status changes to "Cancelled"

---

## Going to Production

When ready for real payments:

1. **Switch to live mode** in Stripe Dashboard (toggle in top-right)

2. **Get live API keys** from Developers → API keys

3. **Create a new webhook endpoint** with your production URL:
   - Endpoint: `https://yourdomain.com/api/payment/webhook`
   - Select the same events as in Step 4

4. **Update environment variables** with live keys:

   ```bash
   STRIPE_SECRET_KEY=sk_live_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx  # From live webhook
   VITE_STRIPE_PUBLIC_KEY=pk_live_xxx
   STRIPE_MONITORING_PRICE_ID=price_xxx  # Create new product in live mode
   ```

5. **Complete Stripe account activation** (requires business details, bank account)

---

## Webhook Event Flow

### One-Time Payment Flow

```
User clicks Pay
    → Payment Intent created
    → User enters card
    → payment_intent.succeeded webhook
    → Job created (if not already via API)
    → Generation starts
```

### Subscription Flow

```
User clicks Subscribe
    → Checkout Session created
    → Redirect to Stripe
    → User completes payment
    → checkout.session.completed webhook
    → Subscription record created
    → Redirect to dashboard
```

### Monthly Renewal

```
Invoice generated
    → invoice.payment_succeeded → Subscription stays active
    → invoice.payment_failed → Handle failed payment
```

### Cancellation

```
User cancels
    → API calls Stripe to cancel
    → customer.subscription.deleted webhook
    → Subscription marked inactive
```

---

## Troubleshooting

### "Invalid signature" webhook error

- Make sure `STRIPE_WEBHOOK_SECRET` matches the webhook endpoint
- For local dev, use the secret from `stripe listen` output
- For production, use the secret from the webhook in Stripe Dashboard

### Subscription not created after payment

- Check webhook logs: `docker-compose logs -f api | grep webhook`
- Verify the `checkout.session.completed` event is being received
- Check that metadata (url, template) is being passed correctly

### Payment succeeds but job not created

- Verify `payment_intent.succeeded` webhook is configured
- Check that the payment intent has metadata (url, template)
- Look for duplicate job checks in logs

### Test webhook manually

```bash
# Trigger a test event
stripe trigger payment_intent.succeeded

# Or trigger subscription events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.deleted
```

### Environment variables not loading

```bash
# Check what's loaded in the container
docker-compose exec api printenv | grep STRIPE

# If showing dummy values, restart with:
docker-compose down && docker-compose up -d
```

### Clear rate limits (if testing repeatedly)

```bash
docker-compose exec redis redis-cli FLUSHALL
```

---

## API Endpoints Reference

### Payment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payment/create-intent` | Create payment intent for one-time payment |
| POST | `/api/payment/webhook` | Stripe webhook handler |

### Subscription Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/subscriptions` | Create subscription (returns checkout URL) |
| GET | `/api/subscriptions` | List all subscriptions |
| GET | `/api/subscriptions/{id}` | Get subscription details |
| POST | `/api/subscriptions/{id}/cancel` | Cancel subscription |
| GET | `/api/subscriptions/{id}/history` | Get monitoring history |

---

## Security Notes

- Never commit `.env` files with real API keys to version control
- Use environment variables for all sensitive configuration
- The webhook signature verification prevents unauthorized webhook calls
- Payment intents are verified with Stripe before creating jobs (prevents fraud)
- Duplicate job prevention ensures each payment only creates one job
