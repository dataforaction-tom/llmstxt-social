# Remove payment gating (llmstxt.social) — design

**Date:** 2026-06-11
**Status:** Approved pending spec review

## Goal

Make the full generation pipeline (enrichment + quality assessment) free for
everyone on llmstxt.social, while keeping all Stripe code in place, dormant
behind a config flag. Monitoring subscriptions (£9/month) remain paid and go
through Stripe unchanged. Open Org is untouched — it has no payment code.

## Decisions (locked)

1. **Unlock features, keep code.** No Stripe code, routes, components, models,
   or migrations are deleted. A config flag turns the one-time payment path
   off; flipping it back restores today's behaviour.
2. **Monitoring stays paid.** Subscription endpoints, Stripe Checkout,
   webhooks, and the monitoring Celery task are unchanged.
3. **Free-tier limits stay.** With payments off, the full pipeline runs under
   the existing 10/day per-IP rate limit with 7-day result expiry.

## Approach

Endpoint-level flag; Celery tasks untouched (chosen over unifying the
free/paid tasks, which would refactor working worker code, and over a flag
inside the task, which risks API/worker config drift).

### Backend (`packages/api`)

- `config.py`: add `payments_enabled: bool = False` (env var
  `PAYMENTS_ENABLED`). Document in `.env.example`.
- `routes/generate.py`:
  - `POST /api/generate/free`: when `payments_enabled` is false, create the
    job with `tier="free"` and 7-day expiry as today, but queue
    `generate_paid_task` (full pipeline: enrichment + assessment) instead of
    `generate_free_task`. Rate limiting unchanged.
  - `POST /api/generate/paid`: when false, return
    `403 {"detail": "One-time payments are currently disabled"}` before any
    Stripe call.
  - `GET /api/assessments`: change filter from `tier == "paid"` to
    `assessment_json IS NOT NULL` so free-tier jobs with assessments appear.
- `routes/payment.py`: `POST /api/payment/create-intent` returns the same 403
  when the flag is false. **The webhook stays live** — subscriptions need it.
- `routes/subscriptions.py`, `services/payment.py`, `tasks/*`: no changes.
- No model or migration changes. `tier`, `payment_intent_id`, `amount_paid`,
  `Subscription`, `MonitoringHistory` all stay.

### Frontend (`packages/web`)

- New `VITE_PAYMENTS_ENABLED` build-time env var (matches the existing
  `VITE_STRIPE_PUBLIC_KEY` pattern; single self-hosted build). Add to
  `vite-env.d.ts` and `.env.example`.
- `Generate.tsx`: when the flag is off, hide the free/paid tier selector,
  never open `PaymentFlow`, always submit via the free endpoint. Assessment
  display already renders whenever `assessment_json` exists — no change.
- `Pricing.tsx`: when off, show two tiers — **Free** (full pipeline:
  enrichment, assessment, 10/day, results last 7 days) and **Monitoring
  £9/month** (unchanged, Stripe). When on, current three-tier layout.
- `PaymentFlow.tsx` stays in the codebase, unreachable while the flag is off.
- `Subscribe.tsx`, `SubscriptionFlow.tsx`, `Dashboard.tsx`: unchanged.

### Error handling

Disabled endpoints fail fast with a clear 403 detail string before touching
Stripe. No silent fallbacks: a paid request while payments are off is an
explicit error, not a redirect to the free path.

### Testing (TDD, per project standard)

Backend (pytest):
- Flag off: free endpoint queues `generate_paid_task` with `tier="free"` and
  7-day expiry; paid endpoint 403s; create-intent 403s; webhook still accepts
  subscription events; assessments endpoint returns free jobs that have
  `assessment_json`.
- Flag on: free endpoint queues `generate_free_task`; paid endpoint and
  create-intent behave as today (regression).

Frontend: `tsc` + lint clean; Vitest tests for Generate-page flag behaviour
following the existing Open Org test patterns.

### Verification

Project checklist applies: pytest green, `/security-review` on changed routes,
docs updated (README + `.env.example`), `docker compose build && up`, no
hardcoded secrets, new env vars documented.

## Out of scope

- Deleting any Stripe code, columns, or migrations.
- Changing rate limits, expiry windows, or the monitoring/subscription flow.
- Any Open Org (openorg.good-ship.co.uk) routes or UI.
- Auth changes (free generation remains unauthenticated).
