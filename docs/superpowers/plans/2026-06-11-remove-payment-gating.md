# Remove Payment Gating (PAYMENTS_ENABLED flag) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the full generation pipeline (enrichment + assessment) free on llmstxt.social, with all Stripe one-time-payment code kept dormant behind a `PAYMENTS_ENABLED` flag; monitoring subscriptions stay paid and untouched.

**Architecture:** Endpoint-level flag. `Settings.payments_enabled` (default `False`) is checked in `routes/generate.py` and `routes/payment.py`. When off, `/api/generate/free` queues the existing full-pipeline Celery task (`generate_paid_task` — verified to take only `(job_id, url, template, sector, goal)`, no payment fields) with `tier="free"` and 7-day expiry; the paid endpoint and create-intent 403. The Stripe webhook, subscriptions routes, services, tasks, models, and migrations are untouched. Frontend mirrors the flag via `VITE_PAYMENTS_ENABLED`.

**Tech Stack:** FastAPI + pydantic-settings + SQLAlchemy async + Celery (backend); React 18 + Vite + TanStack Query + Vitest/RTL (frontend); pytest with `unittest.mock.AsyncMock` route-function tests (see `packages/api/tests/test_open_org_generate_route.py` for the house pattern).

**Spec:** `docs/superpowers/specs/2026-06-11-remove-payment-gating-design.md`

**Conventions for all tasks:**
- Run backend tests from the repo root: `python -m pytest packages/api/tests/... -v` (conftest at `packages/api/tests/conftest.py` provides dummy env vars including Stripe keys).
- Run frontend tests from `packages/web`: `npm test`.
- Commit after every green cycle. Conventional Commits, no AI attribution anywhere.

---

### Task 1: `payments_enabled` setting

**Files:**
- Modify: `packages/api/src/llmstxt_api/config.py` (Stripe block, lines 21-24)
- Test: `packages/api/tests/test_payments_flag.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `packages/api/tests/test_payments_flag.py`:

```python
"""Tests for the PAYMENTS_ENABLED kill switch.

When off (the default), the full pipeline (enrichment + assessment) is free:
/api/generate/free queues the full-pipeline task, and the one-time payment
endpoints refuse with 403. The Stripe webhook and subscriptions routes are
deliberately untouched — monitoring stays paid.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


# --- Settings ---------------------------------------------------------------


def test_payments_disabled_by_default():
    from llmstxt_api.config import Settings

    assert Settings().payments_enabled is False


def test_payments_enabled_via_env(monkeypatch):
    from llmstxt_api.config import Settings

    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    assert Settings().payments_enabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: FAIL — `AttributeError` / pydantic `ValidationError`: `Settings` has no field `payments_enabled`.

- [ ] **Step 3: Add the setting**

In `packages/api/src/llmstxt_api/config.py`, extend the Stripe block (currently lines 21-24):

```python
    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_monitoring_price_id: str | None = None

    # One-time payments kill switch. When False (the default) the free
    # endpoint runs the full pipeline (enrichment + assessment) and the
    # one-time payment endpoints return 403. Monitoring subscriptions are
    # NOT affected — they stay paid via Stripe regardless of this flag.
    payments_enabled: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/config.py packages/api/tests/test_payments_flag.py
git commit -m "feat(api): add PAYMENTS_ENABLED kill switch setting"
```

---

### Task 2: Free endpoint runs the full pipeline when payments are off

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/generate.py:35-75` (`generate_free`)
- Test: `packages/api/tests/test_payments_flag.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `packages/api/tests/test_payments_flag.py`:

```python
# --- Helpers ----------------------------------------------------------------


def make_db():
    """AsyncMock db whose refresh() stamps created_at so JobResponse validates."""
    db = mock.AsyncMock()

    async def fake_refresh(obj):
        obj.created_at = datetime.utcnow()

    db.refresh = mock.AsyncMock(side_effect=fake_refresh)
    return db


def make_http_request():
    http_request = mock.MagicMock()
    http_request.client.host = "203.0.113.7"
    return http_request


# --- /api/generate/free -----------------------------------------------------


@pytest.mark.asyncio
async def test_free_endpoint_runs_full_pipeline_when_payments_disabled():
    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_free
    from llmstxt_api.schemas import GenerateRequest

    db = make_db()
    request = GenerateRequest(url="https://example.org", template="charity")

    free_task = mock.MagicMock()
    paid_task = mock.MagicMock()
    with mock.patch.object(settings, "payments_enabled", False), mock.patch(
        "llmstxt_api.routes.generate.generate_free_task", free_task
    ), mock.patch("llmstxt_api.routes.generate.generate_paid_task", paid_task):
        response = await generate_free(request, make_http_request(), db)

    # Full pipeline queued; the basic free task is bypassed.
    paid_task.delay.assert_called_once()
    free_task.delay.assert_not_called()

    # Free-tier limits unchanged: tier stays "free", expiry stays ~7 days.
    job = db.add.call_args.args[0]
    assert job.tier == "free"
    assert job.expires_at < datetime.utcnow() + timedelta(days=8)
    assert response.tier == "free"


@pytest.mark.asyncio
async def test_free_endpoint_keeps_basic_pipeline_when_payments_enabled():
    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_free
    from llmstxt_api.schemas import GenerateRequest

    db = make_db()
    request = GenerateRequest(url="https://example.org", template="charity")

    free_task = mock.MagicMock()
    paid_task = mock.MagicMock()
    with mock.patch.object(settings, "payments_enabled", True), mock.patch(
        "llmstxt_api.routes.generate.generate_free_task", free_task
    ), mock.patch("llmstxt_api.routes.generate.generate_paid_task", paid_task):
        await generate_free(request, make_http_request(), db)

    free_task.delay.assert_called_once()
    paid_task.delay.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: `test_free_endpoint_runs_full_pipeline_when_payments_disabled` FAILS (`paid_task.delay` not called — `generate_free` unconditionally queues `generate_free_task`). The flag-enabled regression test PASSES (current behaviour). Settings tests still PASS.

- [ ] **Step 3: Implement**

In `packages/api/src/llmstxt_api/routes/generate.py`:

Add the settings import after line 10 (`from llmstxt_api.database import get_db`):

```python
from llmstxt_api.config import settings
```

Replace the queue call at line 72-73:

```python
    # Queue background task
    generate_free_task.delay(str(job.id), str(request.url), request.template, sector, goal)
```

with:

```python
    # Queue background task. With one-time payments disabled, the free tier
    # gets the full pipeline (enrichment + assessment) — same rate limit and
    # 7-day expiry, just no gate. generate_paid_task only needs the job id
    # and generation params; it never reads payment fields.
    if settings.payments_enabled:
        generate_free_task.delay(str(job.id), str(request.url), request.template, sector, goal)
    else:
        generate_paid_task.delay(str(job.id), str(request.url), request.template, sector, goal)
```

Also update the `generate_free` docstring (lines 41-48) to:

```python
    """
    Generate llms.txt (free tier).

    - Rate limited to 10 requests per day per IP
    - Result expires after 7 days
    - When PAYMENTS_ENABLED is false (default), runs the full pipeline
      (enrichment + quality assessment); otherwise basic generation only
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/generate.py packages/api/tests/test_payments_flag.py
git commit -m "feat(api): free endpoint runs full pipeline when payments disabled"
```

---

### Task 3: Paid endpoint 403s when payments are off

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/generate.py:78-150` (`generate_paid`)
- Test: `packages/api/tests/test_payments_flag.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `packages/api/tests/test_payments_flag.py`:

```python
# --- /api/generate/paid -----------------------------------------------------


@pytest.mark.asyncio
async def test_paid_endpoint_403_when_payments_disabled():
    from fastapi import HTTPException

    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_paid
    from llmstxt_api.schemas import GeneratePaidRequest

    db = mock.AsyncMock()
    request = GeneratePaidRequest(
        url="https://example.org", template="charity", payment_intent_id="pi_123"
    )

    with mock.patch.object(settings, "payments_enabled", False):
        with pytest.raises(HTTPException) as exc:
            await generate_paid(request, db, None)

    assert exc.value.status_code == 403
    assert "disabled" in exc.value.detail.lower()
    # Guard fires before any DB or Stripe work.
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_paid_endpoint_still_works_when_payments_enabled():
    from llmstxt_api.config import settings
    from llmstxt_api.routes.generate import generate_paid
    from llmstxt_api.schemas import GeneratePaidRequest

    db = make_db()
    no_existing = mock.MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    db.execute.return_value = no_existing

    request = GeneratePaidRequest(
        url="https://example.org", template="charity", payment_intent_id="pi_123"
    )

    paid_task = mock.MagicMock()
    verify = mock.AsyncMock(return_value={"amount": 900, "metadata": {}})
    with mock.patch.object(settings, "payments_enabled", True), mock.patch(
        "llmstxt_api.routes.generate.verify_payment_intent", verify
    ), mock.patch("llmstxt_api.routes.generate.generate_paid_task", paid_task):
        response = await generate_paid(request, db, None)

    verify.assert_awaited_once_with("pi_123")
    paid_task.delay.assert_called_once()
    assert response.tier == "paid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: `test_paid_endpoint_403_when_payments_disabled` FAILS (no exception raised — endpoint proceeds to the duplicate check). The enabled regression test PASSES.

- [ ] **Step 3: Implement**

In `packages/api/src/llmstxt_api/routes/generate.py`, at the top of `generate_paid` (immediately after the docstring, before the duplicate-job check at line 93):

```python
    # Kill switch: refuse before touching the DB or Stripe. The free
    # endpoint already provides the full pipeline while this is off.
    if not settings.payments_enabled:
        raise HTTPException(
            status_code=403, detail="One-time payments are currently disabled"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/generate.py packages/api/tests/test_payments_flag.py
git commit -m "feat(api): refuse paid generation when payments disabled"
```

---

### Task 4: create-intent 403s when payments are off (webhook untouched)

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/payment.py:27-68` (`create_payment_intent` only — do NOT touch `stripe_webhook`; subscriptions need it)
- Test: `packages/api/tests/test_payments_flag.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `packages/api/tests/test_payments_flag.py`:

```python
# --- /api/payment/create-intent ---------------------------------------------


@pytest.mark.asyncio
async def test_create_intent_403_when_payments_disabled():
    from fastapi import HTTPException

    from llmstxt_api.config import settings
    from llmstxt_api.routes.payment import create_payment_intent
    from llmstxt_api.schemas import CreatePaymentIntentRequest

    request = CreatePaymentIntentRequest(url="https://example.org", template="charity")

    stripe_create = mock.MagicMock()
    with mock.patch.object(settings, "payments_enabled", False), mock.patch(
        "stripe.PaymentIntent.create", stripe_create
    ):
        with pytest.raises(HTTPException) as exc:
            await create_payment_intent(request)

    assert exc.value.status_code == 403
    assert "disabled" in exc.value.detail.lower()
    stripe_create.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_still_processes_subscription_events_when_payments_disabled():
    """Monitoring stays paid: the webhook must keep working with the flag off."""
    from llmstxt_api.config import settings
    from llmstxt_api.routes.payment import stripe_webhook

    db = mock.AsyncMock()
    request = mock.AsyncMock()
    request.body.return_value = b"{}"

    # The route reads event.type / event.data.object as attributes.
    event = mock.MagicMock()
    event.type = "customer.subscription.updated"

    handler = mock.AsyncMock()
    with mock.patch.object(settings, "payments_enabled", False), mock.patch(
        "stripe.Webhook.construct_event", return_value=event
    ), mock.patch(
        "llmstxt_api.routes.payment.handle_subscription_updated", handler
    ):
        response = await stripe_webhook(request, "sig_test", db)

    handler.assert_awaited_once_with(event.data.object, db)
    assert response == {"status": "success"}
```

- [ ] **Step 2: Run tests to verify the new guard test fails**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -k "create_intent or webhook" -v`
Expected: `test_create_intent_403_when_payments_disabled` FAILS — no exception raised (endpoint calls the mocked `stripe.PaymentIntent.create` and returns). `test_webhook_still_processes_subscription_events_when_payments_disabled` PASSES already (the webhook is untouched) — it's a pin against accidentally gating the webhook in Step 3.

- [ ] **Step 3: Implement**

In `packages/api/src/llmstxt_api/routes/payment.py`, at the top of `create_payment_intent` (after the docstring at line 33, before the `try`):

```python
    # Kill switch for one-time payments. The webhook below stays live —
    # monitoring subscriptions depend on it and are not gated by this flag.
    if not settings.payments_enabled:
        raise HTTPException(
            status_code=403, detail="One-time payments are currently disabled"
        )
```

(`settings` and `HTTPException` are already imported in this file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest packages/api/tests/test_payments_flag.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/payment.py packages/api/tests/test_payments_flag.py
git commit -m "feat(api): refuse payment intent creation when payments disabled"
```

---

### Task 5: Assessments list keyed on assessment presence, not tier

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/generate.py:183-208` (`list_user_assessments`)
- Test: `packages/api/tests/test_payments_flag.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `packages/api/tests/test_payments_flag.py`:

```python
# --- /api/assessments -------------------------------------------------------


@pytest.mark.asyncio
async def test_assessments_filter_on_assessment_presence_not_tier():
    from llmstxt_api.models import User
    from llmstxt_api.routes.generate import list_user_assessments

    user = User(id=uuid.uuid4(), email="someone@example.org")

    captured = {}
    db = mock.AsyncMock()

    async def fake_execute(query):
        captured["query"] = query
        result = mock.MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock.AsyncMock(side_effect=fake_execute)

    response = await list_user_assessments(db, user)

    sql = str(captured["query"])
    # Free-tier jobs now carry assessments too, so the dashboard must list
    # anything with an assessment rather than filtering on tier. Note: the
    # SELECT clause names every column including tier, so check for a tier
    # *filter*, not the bare word.
    assert "assessment_json IS NOT NULL" in sql
    assert "tier =" not in sql
    assert response == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest packages/api/tests/test_payments_flag.py::test_assessments_filter_on_assessment_presence_not_tier -v`
Expected: FAIL — `assert "assessment_json IS NOT NULL" in sql` (query currently filters `tier = :tier_1`).

- [ ] **Step 3: Implement**

In `packages/api/src/llmstxt_api/routes/generate.py`, in `list_user_assessments`, replace the filter at line 200:

```python
            GenerationJob.tier == "paid",
```

with:

```python
            GenerationJob.assessment_json.is_not(None),
```

And update the docstring (lines 188-193) to:

```python
    """
    List assessments for the authenticated user.

    Returns completed generation jobs with an assessment that haven't
    expired — any tier, since the full pipeline is free while one-time
    payments are disabled.
    """
```

- [ ] **Step 4: Run the full API suite to verify everything passes**

Run: `python -m pytest packages/api/tests/ -v`
Expected: all PASS (164 existing + 9 new)

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/generate.py packages/api/tests/test_payments_flag.py
git commit -m "feat(api): list assessments by presence rather than paid tier"
```

---

### Task 6: Env, Docker, and deploy wiring

**Files:**
- Modify: `.env.example` (Stripe block)
- Modify: `packages/web/.env.example`
- Modify: `packages/web/src/vite-env.d.ts`
- Modify: `packages/api/Dockerfile:11-14` (web build args)
- Modify: `docker-compose.yml:121-123` (web service environment)
- Modify: `docker-compose.single.yml:36-38, 65-67, 93-95` (three build-args blocks)

No tests for this task — it's config plumbing verified by the Task 9 builds.

- [ ] **Step 1: Root `.env.example`**

In `.env.example`, after the `STRIPE_WEBHOOK_SECRET` line, add:

```bash
# One-time payments kill switch. false (default) = full pipeline (enrichment
# + assessment) is free and one-time payment endpoints return 403. Monitoring
# subscriptions stay paid via Stripe regardless. Keep PAYMENTS_ENABLED and
# VITE_PAYMENTS_ENABLED in sync — the second is baked into the web build.
PAYMENTS_ENABLED=false
VITE_PAYMENTS_ENABLED=false
```

- [ ] **Step 2: Web `.env.example`**

In `packages/web/.env.example`, append:

```bash
# One-time payments kill switch (mirror of the API's PAYMENTS_ENABLED).
# false = tier selector and payment flow hidden; generation is free.
VITE_PAYMENTS_ENABLED=false
```

- [ ] **Step 3: `vite-env.d.ts`**

In `packages/web/src/vite-env.d.ts`, add to `ImportMetaEnv`:

```typescript
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_STRIPE_PUBLIC_KEY: string;
  readonly VITE_PAYMENTS_ENABLED: string;
}
```

- [ ] **Step 4: `packages/api/Dockerfile`**

Extend the web-build args (lines 11-14):

```dockerfile
ARG VITE_API_URL=
ARG VITE_STRIPE_PUBLIC_KEY=
ARG VITE_PAYMENTS_ENABLED=false
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_STRIPE_PUBLIC_KEY=${VITE_STRIPE_PUBLIC_KEY}
ENV VITE_PAYMENTS_ENABLED=${VITE_PAYMENTS_ENABLED}
```

- [ ] **Step 5: Compose files**

In `docker-compose.yml`, web service `environment` block (line 121-123), add:

```yaml
      VITE_PAYMENTS_ENABLED: ${VITE_PAYMENTS_ENABLED:-false}
```

In `docker-compose.single.yml`, add to ALL THREE `build.args` blocks (api ~line 36, worker ~line 65, beat ~line 93):

```yaml
        VITE_PAYMENTS_ENABLED: ${VITE_PAYMENTS_ENABLED:-false}
```

(Do not add to `deploy/scripts/check-env.sh` — that script lists *required* vars and this one has a safe default.)

- [ ] **Step 6: Verify compose files still parse**

Run: `docker compose config --quiet && docker compose -f docker-compose.single.yml config --quiet`
Expected: exit 0, no output (warnings about unset env vars are fine).

- [ ] **Step 7: Commit**

```bash
git add .env.example packages/web/.env.example packages/web/src/vite-env.d.ts packages/api/Dockerfile docker-compose.yml docker-compose.single.yml
git commit -m "chore: wire PAYMENTS_ENABLED through env and docker builds"
```

---

### Task 7: Frontend flag module + Generate page

**Files:**
- Create: `packages/web/src/config/payments.ts`
- Modify: `packages/web/src/pages/Generate.tsx`
- Test: `packages/web/src/pages/Generate.test.tsx` (new file)

- [ ] **Step 1: Create the flag module**

Create `packages/web/src/config/payments.ts`:

```typescript
/**
 * One-time payments kill switch — mirror of the API's PAYMENTS_ENABLED.
 * When off, the tier selector and payment flow are hidden and every
 * generation goes through the free endpoint, which the API upgrades to
 * the full pipeline (enrichment + assessment). Monitoring subscriptions
 * are not affected by this flag.
 */
export function paymentsEnabled(): boolean {
  return import.meta.env.VITE_PAYMENTS_ENABLED === 'true';
}
```

(A function rather than a const so tests can swap it per-case with `vi.mocked(...).mockReturnValue(...)`.)

- [ ] **Step 2: Write the failing tests**

Create `packages/web/src/pages/Generate.test.tsx` (pattern follows `src/pages/openorg/Generate.test.tsx`):

```tsx
/**
 * Payments-flag behaviour on the llmstxt.social Generate page: with payments
 * off the tier selector disappears and the submit button is plain "Generate";
 * with payments on the current free/paid radiogroup renders.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import GeneratePage from './Generate';
import { paymentsEnabled } from '../config/payments';

vi.mock('../config/payments', () => ({ paymentsEnabled: vi.fn(() => false) }));
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: null }) }));
// PaymentFlow calls loadStripe at module scope — keep it out of the test env.
vi.mock('../components/PaymentFlow', () => ({ default: () => null }));
vi.mock('../components/SEOHead', () => ({ default: () => null }));
vi.mock('../components/SchemaScript', () => ({
  default: () => null,
  generateHowToSchema: () => ({}),
}));
vi.mock('../api/client', () => ({
  default: {
    getTemplateOptions: vi.fn().mockResolvedValue({
      template: 'charity',
      sectors: [],
      goals: [],
      default_sector: 'general',
      default_goal: 'more_donors',
    }),
    generateFree: vi.fn(),
    getJob: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <GeneratePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GeneratePage payments flag', () => {
  beforeEach(() => {
    vi.mocked(paymentsEnabled).mockReturnValue(false);
  });

  it('hides the tier selector and shows a plain Generate button when payments are off', () => {
    renderPage();
    expect(
      screen.queryByRole('radiogroup', { name: /pricing tier/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /^generate$/i }),
    ).toBeInTheDocument();
  });

  it('shows the tier selector when payments are on', () => {
    vi.mocked(paymentsEnabled).mockReturnValue(true);
    renderPage();
    expect(
      screen.getByRole('radiogroup', { name: /pricing tier/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /generate free/i }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/web && npm test -- src/pages/Generate.test.tsx`
Expected: first test FAILS (radiogroup is rendered, button says "Generate Free"); second test PASSES.

- [ ] **Step 4: Implement in `Generate.tsx`**

All edits to `packages/web/src/pages/Generate.tsx`:

(a) Add the import after the `useAuth` import (line 11):

```tsx
import { paymentsEnabled } from '../config/payments';
```

(b) Replace the module-level `howToSteps` const (lines 13-19) with a builder so the tier step disappears when payments are off:

```tsx
function buildHowToSteps(payments: boolean) {
  return [
    { name: 'Enter your URL', text: 'Enter your organisation\'s website URL in the form' },
    { name: 'Select a template', text: 'Choose from Charity, Funder, Public Sector, or Startup template' },
    ...(payments
      ? [{ name: 'Choose your tier', text: 'Select Free for basic generation or Paid for full assessment' }]
      : []),
    { name: 'Generate', text: 'Click generate and wait for your AI-powered llms.txt file' },
    { name: 'Download', text: 'Download your llms.txt file and add it to your website root' },
  ];
}
```

(c) Inside the component, read the flag once (after the `useAuth` line, line 22):

```tsx
  const payments = paymentsEnabled();
```

(d) Update `handleSubmit` (lines 67-75) so the payment branch only exists when payments are on:

```tsx
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (payments && tier === 'paid') {
      setShowPayment(true);
    } else {
      generateMutation.mutate();
    }
  };
```

(e) Update the `SchemaScript` usage (lines 104-108) to use the builder:

```tsx
      <SchemaScript schema={generateHowToSchema(
        'How to Generate an llms.txt File',
        'Create AI-ready documentation for your organisation in 5 simple steps',
        buildHowToSteps(payments)
      )} />
```

(f) Wrap the entire tier `<fieldset>` (lines 207-256) in the flag:

```tsx
            {/* Tier Selection (hidden while one-time payments are off) */}
            {payments && (
              <fieldset>
                ...existing fieldset content unchanged...
              </fieldset>
            )}
```

(g) Update the submit-button label (line 270):

```tsx
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="inline-block animate-spin mr-2" />
                  Generating...
                </>
              ) : payments ? (
                <>Generate {tier === 'paid' ? '(Proceed to Payment)' : 'Free'}</>
              ) : (
                <>Generate</>
              )}
```

Leave the `showPayment` modal block, `handlePaymentSuccess`, tier state, and everything else unchanged — unreachable while the flag is off, intact for when it's flipped back.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/web && npm test -- src/pages/Generate.test.tsx`
Expected: 2 PASS

- [ ] **Step 6: Type-check and lint**

Run: `cd packages/web && npx tsc --noEmit && npm run lint`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add packages/web/src/config/payments.ts packages/web/src/pages/Generate.tsx packages/web/src/pages/Generate.test.tsx
git commit -m "feat(web): hide tier selector and payment flow when payments off"
```

---

### Task 8: Pricing page reflects the flag

**Files:**
- Modify: `packages/web/src/pages/Pricing.tsx`
- Test: `packages/web/src/pages/Pricing.test.tsx` (new file)

- [ ] **Step 1: Write the failing tests**

Create `packages/web/src/pages/Pricing.test.tsx`:

```tsx
/**
 * Payments-flag behaviour on the Pricing page: with payments off the £9
 * one-time tier disappears and Free advertises the full pipeline; with
 * payments on the current three-tier layout renders.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import PricingPage from './Pricing';
import { paymentsEnabled } from '../config/payments';

vi.mock('../config/payments', () => ({ paymentsEnabled: vi.fn(() => false) }));
vi.mock('../components/SEOHead', () => ({ default: () => null }));
vi.mock('../components/SchemaScript', () => ({
  default: () => null,
  generateFAQSchema: () => ({}),
  generateProductSchema: () => ({}),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <PricingPage />
    </MemoryRouter>,
  );
}

describe('PricingPage payments flag', () => {
  beforeEach(() => {
    vi.mocked(paymentsEnabled).mockReturnValue(false);
  });

  it('shows Free (full pipeline) and Subscription only when payments are off', () => {
    renderPage();
    const tiers = screen.getAllByRole('listitem');
    expect(tiers).toHaveLength(2);
    expect(screen.queryByText(/one-time/i)).not.toBeInTheDocument();
    // Free tier now advertises the formerly-paid features.
    expect(screen.getByText('Full quality assessment')).toBeInTheDocument();
    expect(screen.getByText('Charity Commission enrichment')).toBeInTheDocument();
  });

  it('shows all three tiers when payments are on', () => {
    vi.mocked(paymentsEnabled).mockReturnValue(true);
    renderPage();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText(/one-time/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/web && npm test -- src/pages/Pricing.test.tsx`
Expected: first test FAILS (3 listitems); second PASSES.

- [ ] **Step 3: Implement in `Pricing.tsx`**

Restructure `packages/web/src/pages/Pricing.tsx`. Keep `PricingCard` and `FAQItem` exactly as they are. Replace the FAQ const and the `PricingPage` component:

(a) Add the import:

```tsx
import { paymentsEnabled } from '../config/payments';
```

(b) Replace the single `pricingFAQs` const (lines 6-31) with two lists — rename the existing one and add a free-mode variant. The existing array stays verbatim as `paidModeFAQs`:

```tsx
const paidModeFAQs = [
  ...the six existing entries, unchanged...
];

const freeModeFAQs = [
  {
    question: "What's included in the free tier?",
    answer: "Everything: full llms.txt generation with AI-powered quality assessment and enrichment data from external sources. You can generate up to 10 files per day and results are stored for 7 days.",
  },
  {
    question: "What is enrichment data?",
    answer: "Enrichment data includes official information from the Charity Commission (for charities) and 360Giving (for funders). This adds verified details about registration numbers, financial data, and grant history to your llms.txt file.",
  },
  {
    question: "How does the quality assessment work?",
    answer: "Our AI-powered assessment analyzes your llms.txt file for completeness, clarity, and compliance with the specification. You'll receive a detailed report with scores, findings, and actionable recommendations to improve your file.",
  },
  {
    question: "What does the subscription add?",
    answer: "The subscription (£9/month) includes automatic monitoring — we'll regenerate your llms.txt whenever your website changes, notify you of updates, and keep a change history in your dashboard.",
  },
  {
    question: "Can I use this for multiple organisations?",
    answer: "Yes! Each generation is per URL, so you can generate llms.txt files for as many organisations as you need, within the daily limit.",
  },
  {
    question: "Do you support organisations outside the UK?",
    answer: "Currently, we specialize in UK social sector organisations (charities, funders, public sector). Our enrichment integrations are UK-specific (Charity Commission, 360Giving). However, the basic generation works for any organisation worldwide.",
  },
];
```

(c) Rewrite `PricingPage` to branch on the flag and render FAQs from the array (this also removes the existing duplication between `pricingFAQs` and the hand-written `FAQItem` list):

```tsx
export default function PricingPage() {
  const payments = paymentsEnabled();
  const faqs = payments ? paidModeFAQs : freeModeFAQs;

  return (
    <>
      <SEOHead
        title="Pricing"
        canonicalPath="/pricing"
        description={
          payments
            ? 'Simple, transparent pricing for llms.txt generation. Free tier for basic generation, £9 one-time for full assessment, or £9/month for automated monitoring.'
            : 'llms.txt generation with full AI assessment is free. Add automated monitoring for £9/month.'
        }
      />
      <SchemaScript schema={generateFAQSchema(faqs)} />
      <SchemaScript schema={generateProductSchema()} />
      <div className="bg-gray-50 py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-gray-600">
            {payments
              ? 'Choose the tier that works for your organization'
              : 'Generation with full assessment is free — add monitoring if you want it'}
          </p>
        </div>

        <div
          className={`grid gap-8 mx-auto ${payments ? 'md:grid-cols-3 max-w-6xl' : 'md:grid-cols-2 max-w-4xl'}`}
          role="list"
          aria-label="Pricing tiers"
        >
          {payments ? (
            <>
              {/* Free Tier */}
              <PricingCard
                name="Free"
                price="£0"
                period=""
                description="Try it out with basic generation"
                features={[
                  '10 generations per day',
                  'All 4 templates',
                  'Basic llms.txt generation',
                  'No enrichment data',
                  'No quality assessment',
                  'Results expire after 7 days',
                ]}
                cta="Get Started Free"
                ctaLink="/generate"
                highlighted={false}
              />

              {/* Paid Tier */}
              <PricingCard
                name="Paid"
                price="£9"
                period="one-time"
                description="Full generation with assessment"
                features={[
                  'All 4 templates',
                  'Charity Commission enrichment',
                  '360Giving data for funders',
                  'Full quality assessment',
                  'AI-powered analysis',
                  'Website gap detection',
                  'JSON + Markdown reports',
                  'Valid for 30 days',
                ]}
                cta="Generate with Assessment"
                ctaLink="/generate"
                highlighted={true}
              />
            </>
          ) : (
            <PricingCard
              name="Free"
              price="£0"
              period=""
              description="Full generation with assessment — free"
              features={[
                '10 generations per day',
                'All 4 templates',
                'Charity Commission enrichment',
                '360Giving data for funders',
                'Full quality assessment',
                'AI-powered analysis',
                'Website gap detection',
                'Results expire after 7 days',
              ]}
              cta="Get Started Free"
              ctaLink="/generate"
              highlighted={true}
            />
          )}

          {/* Subscription Tier (always shown — monitoring stays paid) */}
          <PricingCard
            name="Subscription"
            price="£9"
            period="per month"
            description="Automated monitoring and updates"
            features={[
              payments ? 'All paid tier features' : 'Everything in Free',
              'Monthly monitoring',
              'Auto-regeneration on changes',
              'Email notifications',
              'Change history tracking',
              'Comparison reports',
              'Dashboard access',
              'Cancel anytime',
            ]}
            cta="Subscribe Now"
            ctaLink="/subscribe"
            highlighted={false}
          />
        </div>

        {/* FAQs */}
        <div className="mt-20 max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            {faqs.map((faq) => (
              <FAQItem key={faq.question} question={faq.question} answer={faq.answer} />
            ))}
          </div>
        </div>
      </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && npm test -- src/pages/Pricing.test.tsx`
Expected: 2 PASS

- [ ] **Step 5: Type-check and lint**

Run: `cd packages/web && npx tsc --noEmit && npm run lint`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add packages/web/src/pages/Pricing.tsx packages/web/src/pages/Pricing.test.tsx
git commit -m "feat(web): pricing page shows free full pipeline when payments off"
```

---

### Task 9: Full verification, security review, docs

**Files:**
- Possibly modify: `README.md` (env var docs), `STATE.md` / `HANDOFF.md` (tracking files — keep current per project rules)

- [ ] **Step 1: Full backend suite**

Run: `python -m pytest packages/api/tests/ packages/core/tests/ tests/ -v` (skip dirs that don't exist)
Expected: all PASS

- [ ] **Step 2: Full frontend verification**

Run: `cd packages/web && npm test && npm run build && npm run lint`
Expected: tests PASS, build succeeds, lint clean

- [ ] **Step 3: Docker build**

Run: `docker compose build`
Expected: succeeds

- [ ] **Step 4: Hardcoded-secrets check**

Run: `grep -rn "sk-" packages/ --include="*.py" --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v test`
Expected: no real keys (dummy test values in conftest are fine)

- [ ] **Step 5: Security review**

Invoke the project's `/security-review` skill on the changed routes (`routes/generate.py`, `routes/payment.py`). Key things it should confirm: the 403 guards fire before any DB/Stripe work; the webhook signature verification is untouched; no new unauthenticated data exposure from the assessments filter change (still scoped to `user_id == user.id`).

- [ ] **Step 6: Docs**

Invoke the project's `docs-updater` skill. At minimum:
- README: document `PAYMENTS_ENABLED` / `VITE_PAYMENTS_ENABLED` wherever env vars are listed.
- Update `STATE.md`/`HANDOFF.md` if this work intersects their scope (this is outside the Open Org 11-step plan — a one-line note is enough).

- [ ] **Step 7: Commit docs**

```bash
git add README.md STATE.md HANDOFF.md
git commit -m "docs: document PAYMENTS_ENABLED kill switch"
```

(Adjust the file list to what actually changed.)

---

## Out of scope (do not touch)

- `routes/subscriptions.py`, `services/payment.py` internals, `tasks/monitor.py`, the Stripe webhook handler — monitoring stays paid.
- Models, schemas, alembic migrations — no DB changes.
- `Subscribe.tsx`, `SubscriptionFlow.tsx`, `Dashboard.tsx`, `PaymentFlow.tsx` (stays in tree, unreachable while flag is off).
- Anything under Open Org (`open_org_*` routes, `packages/web/src/pages/openorg/`).
- The free-tier rate limit TODO in `generate_free` (pre-existing, separate concern).
