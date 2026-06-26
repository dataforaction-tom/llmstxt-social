# Open Org test deployment to `openorg.good-ship.co.uk`

**Date:** 2026-06-26
**Branch:** `fix/openorg-hardening`
**Status:** Approved design — ready for implementation plan

## Goal

Make the current Open Org build (ideas-first discovery, graph view, evidence/
signalling) testable on the public web at `openorg.good-ship.co.uk`, with
working navigation and magic-link email login, **without breaking the live
`llmstxt.social` product** that shares the same FastAPI process.

## Context (current state)

- One FastAPI process on `localhost:8000` serves both the API and the React SPA
  for **both** hostnames. Routing: Cloudflare DNS → Cloudflare Tunnel → Caddy →
  FastAPI. The Caddyfile already has an `openorg.good-ship.co.uk` block.
- The SPA selects its route tree and nav from `window.location.hostname`. The
  Open Org nav (brand "Open Org"; Discover / About / Generate Profile; Log in /
  logged-in state; Good Ship footer) already exists in `Layout.tsx` under the
  `isOpenOrg = hostname.startsWith('openorg.')` branch. It renders correctly on
  `openorg.*` hosts (verified via `openorg.localhost:3000`); locally on plain
  `localhost` the llms.txt nav shows because the gate doesn't match. **Nav needs
  no new work.**
- Magic-link login is the **shared** `/auth/magic-link` + `/auth/verify` in
  `routes/auth.py`. The link is built from a single global `settings.frontend_url`,
  and the email is llms.txt-branded (`from = settings.from_email`, subject
  "Your llms.txt login link"). `routes/open_org_auth.py` only adds org-admin /
  claim-token logic and reuses `require_auth`.
- The live prod image predates all Open Org code and is stale; it must be
  rebuilt + force-recreated to deploy (this staleness is what crashed the graph
  view through the tunnel). Postgres + Redis are shared between products.

## Decisions

- **Hosting:** shared FastAPI process (no isolated stack).
- **Email:** add Open Org branding (subject/heading + Good Ship from-address)
  when the request originates from the Open Org host.
- **Code promotion:** commit the remaining ideas-first WIP on
  `fix/openorg-hardening` and deploy **from that branch**; no master merge yet.
- **Auth cookie:** leave `AUTH_COOKIE_DOMAIN` **unset** (host-only cookies).
- **Out of scope:** cross-product SSO, Murmurations registration, key rotation,
  isolated second stack.

## Workstream 1 — Auth: request-aware magic link

**Problem:** a single global `frontend_url` can only be correct for one of the
two hostnames served by the one process. Pointing it at Open Org would break
`llmstxt.social` login emails (links to the wrong host), and vice versa.

**Change:** in `/auth/magic-link`, derive the link's base URL from the incoming
request's `Origin` header, **validated against an allowlist**, falling back to
`settings.frontend_url` when the header is absent or unrecognised.

- Allowlist (config-driven, env-overridable): `https://llmstxt.social`,
  `https://openorg.good-ship.co.uk`, and `http://localhost:*` /
  `http://openorg.localhost:*` for dev.
- **Security-critical:** never build a login link from an unvalidated
  `Host`/`Origin` — that is a host-header-injection / token-phishing vector.
  Unknown origins fall back to the configured `frontend_url`; attacker input is
  never reflected into the emailed link.
- `AUTH_COOKIE_DOMAIN` stays unset → host-only cookie on
  `openorg.good-ship.co.uk`. `llmstxt.social` auth is untouched.

**Tests (TDD):**
- Allowed Open Org origin → link uses `https://openorg.good-ship.co.uk`.
- Allowed llms.txt origin → link uses `https://llmstxt.social`.
- Unknown/spoofed origin → link falls back to `frontend_url`, never the spoofed
  host.
- No `Origin` header → falls back to `frontend_url`.
- `/security-review` pass on the changed endpoint.

## Workstream 2 — Email / Resend (Open Org branding + delivery)

**Code (me):**
- Host-aware email content: when the request origin is the Open Org host, use an
  "Open Org" subject + heading + button and a Good Ship `from` address; otherwise
  keep the existing llms.txt copy. Reuse the same allowlist/host signal as
  Workstream 1.
- Dev-mode stdout path (`environment == development`) continues to log the link
  without calling Resend.

**Manual (user) — prerequisites for real delivery:**
- Verify the sending domain in Resend (DNS records for `good-ship.co.uk` and/or
  `openorg.good-ship.co.uk`).
- Set prod env: `RESEND_API_KEY`, `FROM_EMAIL` (e.g. `hello@openorg.good-ship.co.uk`).
- Until the domain is verified, Resend sends fail (the endpoint returns 500).

## Workstream 3 — Deploy (shared-infra procedure)

1. **Commit remaining WIP** on `fix/openorg-hardening`: `Discover.tsx`,
   `api/openorg.ts`, `routes/open_org_discovery.py`, `Discover.test.tsx` (the
   stable-mock fix), and `tests/test_open_org_idea_browser.py`. All web + API
   tests green and `npm run build` succeeds first.
2. **User — Cloudflare Tunnel route:**
   `cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk`
   (or via the Zero Trust UI). Caddy block already present.
3. **Prod env vars:** `CORS_ORIGINS` includes `https://openorg.good-ship.co.uk`;
   `FRONTEND_URL` set as the fallback; `AUTH_COOKIE_DOMAIN` unset; LLM provider
   keys present; `RESEND_API_KEY` + `FROM_EMAIL` set.
4. **Deploy (documented procedure; mind compose file order):** check out
   `fix/openorg-hardening` on the Mac Mini → `docker compose build` →
   `alembic upgrade head` (applies `org_signals` and any pending migrations on
   the shared DB) → force-recreate the five services (api, worker,
   celery_worker, beat, celery_beat).

## Impact on `llmstxt.social`

- **Deploy-time:** brief shared restart; llms.txt is bumped to the deployed
  branch's code (it was on a stale image). Branch must keep llms.txt healthy.
- **Auth:** no breakage — request-aware link keeps llms.txt magic links pointing
  at llms.txt; host-only cookie leaves llms.txt sessions alone.
- **Visual:** none — the layout is hostname-gated; llms.txt keeps its own nav.
- **DB:** additive migrations (new tables) on the shared Postgres; low risk.

## Verification (definition of done)

- Auth change: TDD green + `/security-review` pass.
- Full API (`pytest`) and web (`vitest`) suites green; `docker compose build`
  succeeds.
- Post-deploy smoke:
  1. `https://openorg.good-ship.co.uk` loads with the Open Org nav.
  2. Graph view renders (no stale-bundle crash).
  3. A real Open Org magic-link email arrives and logs in.
  4. **`llmstxt.social` still logs in** — the critical regression check.

## Risks / open items

- Resend domain verification is a hard external dependency for real email; the
  deploy can otherwise proceed (login then blocked only by delivery).
- Deploying the branch (not master) means prod runs un-merged code; acceptable
  for a test surface, to be reconciled when promoting to master.
