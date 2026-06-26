# Open Org Test Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the current Open Org build to `openorg.good-ship.co.uk` on the shared FastAPI process, with working nav and magic-link email login, without breaking live `llmstxt.social`.

**Architecture:** One FastAPI process serves both hostnames. The only code change is making the magic-link base URL and email branding derive from the request's validated `Origin` (allowlist), so one process serves correct login links for both products. Everything else is config + a deploy runbook.

**Tech Stack:** FastAPI, Pydantic settings, Resend, Alembic, Docker Compose, Caddy, Cloudflare Tunnel, React/Vite SPA, pytest, vitest.

## Global Constraints

- Conventional Commits; subject ≤72 chars; no AI/Claude attribution anywhere.
- Work on branch `fix/openorg-hardening`; never commit to `master`; never `--no-verify`.
- Secrets via env only; never hardcode keys.
- `AUTH_COOKIE_DOMAIN` stays **unset** in prod (host-only cookies).
- Allowlist hosts (prod): `https://llmstxt.social`, `https://openorg.good-ship.co.uk`. Dev also allows `http://localhost:3000`, `http://localhost:5173`, `http://openorg.localhost:3000`.
- Open Org `from` address: `Open Org <hello@openorg.good-ship.co.uk>` (must be on a Resend-verified domain).
- Deploy the **branch**, not master. Five services to recreate: api, worker, celery_worker, beat, celery_beat.

---

### Task 1: Commit the remaining ideas-first WIP (green first)

Prerequisite: deploy builds from committed code. The ideas-first feature + the `Discover.test.tsx` stable-mock fix are currently uncommitted.

**Files (all already modified in working tree):**
- `packages/api/src/llmstxt_api/routes/open_org_discovery.py`
- `packages/api/tests/test_open_org_idea_browser.py`
- `packages/web/src/api/openorg.ts`
- `packages/web/src/pages/openorg/Discover.tsx`
- `packages/web/src/pages/openorg/Discover.test.tsx` (untracked — the stable-mock fix)

- [ ] **Step 1: Run the web suite, confirm green**

Run: `cd packages/web && CI=true npx vitest run`
Expected: all files pass, including `src/pages/openorg/Discover.test.tsx` (7 passed) and `GraphDiscovery.test.tsx` (22 passed). No hang.

- [ ] **Step 2: Run the API idea-browser tests, confirm green**

Run: `cd packages/api && pytest tests/test_open_org_idea_browser.py -q`
Expected: PASS.

- [ ] **Step 3: Confirm the web build compiles**

Run: `cd packages/web && npm run build`
Expected: build succeeds (no TS/transform errors).

- [ ] **Step 4: Commit the ideas-first feature + test fix**

```bash
git add packages/api/src/llmstxt_api/routes/open_org_discovery.py \
        packages/api/tests/test_open_org_idea_browser.py \
        packages/web/src/api/openorg.ts \
        packages/web/src/pages/openorg/Discover.tsx \
        packages/web/src/pages/openorg/Discover.test.tsx
git commit -m "feat(openorg): ideas-first discovery with sort, signals, and summary"
```

---

### Task 2: Request-aware magic-link base URL

Make `/auth/magic-link` build the link from the request's validated `Origin`, falling back to `settings.frontend_url`. Security-critical: never reflect an unvalidated host into the emailed link.

**Files:**
- Modify: `packages/api/src/llmstxt_api/config.py` (add `magic_link_origin_allowlist`)
- Modify: `packages/api/src/llmstxt_api/routes/auth.py` (helper + endpoint signature + link build)
- Test: `packages/api/tests/test_magic_link_origin.py` (create)

**Interfaces:**
- Produces: `auth._allowed_origins() -> set[str]`, `auth._resolve_frontend_base(http_request: Request | None) -> str`.
- `send_magic_link(request: MagicLinkRequest, http_request: Request | None = None, db = Depends(get_db))` — `http_request` defaults to `None` so existing 2-arg unit tests (`test_dev_magic_link_logger.py`) keep working.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/test_magic_link_origin.py`:

```python
"""The magic-link base URL must come from the request's validated Origin,
never an unvalidated/spoofed host. Falls back to settings.frontend_url."""
from __future__ import annotations

from unittest import mock
import pytest


def _req(origin: str | None):
    headers = {"origin": origin} if origin else {}
    return mock.Mock(headers=headers)


def test_allowed_openorg_origin_is_used():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist",
        "https://llmstxt.social,https://openorg.good-ship.co.uk",
    ), mock.patch.object(auth.settings, "environment", "production"):
        base = auth._resolve_frontend_base(_req("https://openorg.good-ship.co.uk"))
    assert base == "https://openorg.good-ship.co.uk"


def test_allowed_llmstxt_origin_is_used():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist",
        "https://llmstxt.social,https://openorg.good-ship.co.uk",
    ), mock.patch.object(auth.settings, "environment", "production"):
        base = auth._resolve_frontend_base(_req("https://llmstxt.social"))
    assert base == "https://llmstxt.social"


def test_spoofed_origin_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "magic_link_origin_allowlist", "https://llmstxt.social",
    ), mock.patch.object(auth.settings, "environment", "production"), \
         mock.patch.object(auth.settings, "frontend_url", "https://llmstxt.social"):
        base = auth._resolve_frontend_base(_req("https://evil.example.com"))
    assert base == "https://llmstxt.social"
    assert "evil.example.com" not in base


def test_missing_origin_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "frontend_url", "http://localhost:3000"):
        base = auth._resolve_frontend_base(_req(None))
    assert base == "http://localhost:3000"


def test_none_request_falls_back_to_frontend_url():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "frontend_url", "http://localhost:3000"):
        assert auth._resolve_frontend_base(None) == "http://localhost:3000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_magic_link_origin.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_resolve_frontend_base'`.

- [ ] **Step 3: Add the allowlist setting**

In `packages/api/src/llmstxt_api/config.py`, after the `frontend_url` line (≈line 66) add:

```python
    # Comma-separated origins allowed to set the magic-link base URL (one
    # FastAPI process serves multiple hostnames). Anything not listed falls
    # back to frontend_url — never reflect an unvalidated Origin into a login
    # link (host-header injection / token phishing).
    magic_link_origin_allowlist: str = (
        "https://llmstxt.social,https://openorg.good-ship.co.uk"
    )
```

- [ ] **Step 4: Add the helper + wire it into the endpoint**

In `packages/api/src/llmstxt_api/routes/auth.py`, add `Request` to the FastAPI import:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, Request
```

Add helpers above `send_magic_link`:

```python
def _allowed_origins() -> set[str]:
    configured = {
        o.strip()
        for o in settings.magic_link_origin_allowlist.split(",")
        if o.strip()
    }
    if settings.environment == "development":
        configured |= {
            "http://localhost:3000",
            "http://localhost:5173",
            "http://openorg.localhost:3000",
        }
    return configured


def _resolve_frontend_base(http_request: Request | None) -> str:
    """Pick the SPA base URL for the magic link. Uses the request Origin only
    if it is on the allowlist; otherwise falls back to the configured
    frontend_url. Never returns an unvalidated host."""
    if http_request is not None:
        origin = http_request.headers.get("origin")
        if origin and origin in _allowed_origins():
            return origin
    return settings.frontend_url
```

Change the endpoint signature (≈line 91) and link build (≈line 124):

```python
async def send_magic_link(
    request: MagicLinkRequest,
    http_request: Request | None = None,
    db: AsyncSession = Depends(get_db),
):
```

```python
    magic_link = f"{_resolve_frontend_base(http_request)}/auth/verify?token={token}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/api && pytest tests/test_magic_link_origin.py tests/test_dev_magic_link_logger.py -q`
Expected: all PASS (new origin tests + the pre-existing dev-logger tests still green via the `None` default).

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/llmstxt_api/config.py \
        packages/api/src/llmstxt_api/routes/auth.py \
        packages/api/tests/test_magic_link_origin.py
git commit -m "fix(auth): derive magic-link base URL from validated request Origin"
```

---

### Task 3: Host-aware Open Org email branding

When the resolved base is the Open Org host, send an Open Org-branded email from the Good Ship address; otherwise keep the llms.txt copy.

**Files:**
- Modify: `packages/api/src/llmstxt_api/config.py` (add `openorg_from_email`)
- Modify: `packages/api/src/llmstxt_api/routes/auth.py` (branding helper + use in send)
- Test: `packages/api/tests/test_magic_link_branding.py` (create)

**Interfaces:**
- Produces: `auth._email_branding(base_url: str) -> dict` with keys `from_email`, `subject`, `html` (html takes the already-built `magic_link`). Signature used by Task 3 only.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/test_magic_link_branding.py`:

```python
"""Magic-link emails are Open Org-branded when the base URL is the Open Org
host, llms.txt-branded otherwise."""
from __future__ import annotations
from unittest import mock


def test_openorg_base_uses_openorg_branding():
    from llmstxt_api.routes import auth
    with mock.patch.object(
        auth.settings, "openorg_from_email", "Open Org <hello@openorg.good-ship.co.uk>"
    ):
        b = auth._email_branding("https://openorg.good-ship.co.uk")
    assert b["from_email"] == "Open Org <hello@openorg.good-ship.co.uk>"
    assert "Open Org" in b["subject"]
    assert "llms.txt" not in b["subject"]


def test_llmstxt_base_uses_default_branding():
    from llmstxt_api.routes import auth
    with mock.patch.object(auth.settings, "from_email", "llmstxt <x@resend.dev>"):
        b = auth._email_branding("https://llmstxt.social")
    assert b["from_email"] == "llmstxt <x@resend.dev>"
    assert "llms.txt" in b["subject"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_magic_link_branding.py -q`
Expected: FAIL — `_email_branding` not defined.

- [ ] **Step 3: Add the from-address setting**

In `packages/api/src/llmstxt_api/config.py`, after the `from_email` line (≈line 51) add:

```python
    # From-address for Open Org magic-link emails (must be a Resend-verified
    # domain). Used when the login originates from the Open Org host.
    openorg_from_email: str = "Open Org <hello@openorg.good-ship.co.uk>"
```

- [ ] **Step 4: Add the branding helper + use it**

In `packages/api/src/llmstxt_api/routes/auth.py`, add below `_resolve_frontend_base`:

```python
def _email_branding(base_url: str) -> dict:
    """Subject / from / html for the login email, branded by host."""
    is_openorg = "openorg." in base_url
    if is_openorg:
        return {
            "from_email": settings.openorg_from_email,
            "subject": "Your Open Org login link",
            "product": "Open Org",
            "accent": "#2D8B7A",
        }
    return {
        "from_email": settings.from_email,
        "subject": "Your llms.txt login link",
        "product": "llms.txt",
        "accent": "#6366f1",
    }
```

Replace the Resend send block (the `resend.Emails.send({...})` call, ≈lines 146-167) with branding-driven values:

```python
    brand = _email_branding(_resolve_frontend_base(http_request))
    try:
        resend.Emails.send({
            "from": brand["from_email"],
            "to": [email],
            "subject": brand["subject"],
            "html": f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: {brand['accent']};">Log in to {brand['product']}</h2>
                    <p>Click the button below to log in. This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
                    <a href="{magic_link}"
                       style="display: inline-block; background: {brand['accent']}; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 8px; margin: 16px 0;">
                        Log in to {brand['product']}
                    </a>
                    <p style="color: #666; font-size: 14px;">
                        If you didn't request this link, you can safely ignore this email.
                    </p>
                    <p style="color: #666; font-size: 12px; margin-top: 32px;">
                        Or copy this link: {magic_link}
                    </p>
                </div>
            """,
        })
    except Exception as e:
        print(f"Failed to send magic link email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/api && pytest tests/test_magic_link_branding.py tests/test_dev_magic_link_logger.py -q`
Expected: all PASS (branding tests green; production-send test still calls Resend once).

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/llmstxt_api/config.py \
        packages/api/src/llmstxt_api/routes/auth.py \
        packages/api/tests/test_magic_link_branding.py
git commit -m "feat(auth): Open Org branding for magic-link emails by host"
```

---

### Task 4: Security review of the auth change

- [ ] **Step 1: Run the project security review on the changed auth code**

Invoke `/security-review` (project skill) over `packages/api/src/llmstxt_api/routes/auth.py` and `config.py`. Confirm specifically:
- The Origin is matched by **exact string** against the allowlist (no `startswith`/substring bypass like `https://llmstxt.social.evil.com`).
- Unknown/missing Origin falls back to `frontend_url`; attacker host never reaches the emailed link.
- No secrets or tokens logged outside the existing dev-mode path.

- [ ] **Step 2: Address any findings, then re-run the API suite**

Run: `cd packages/api && pytest tests/test_magic_link_origin.py tests/test_magic_link_branding.py tests/test_dev_magic_link_logger.py tests/test_auth_cookie_domain.py -q`
Expected: PASS.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix(auth): address security review on magic-link origin handling"
```
(Skip the commit if the review found nothing.)

---

### Task 5: Deploy config — env + docs

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md` (Known issues — note the magic-link is now request-aware)

- [ ] **Step 1: Document the new env in `.env.example`**

Add near the auth/email section:

```bash
# Origins allowed to set the magic-link base URL (one process, many hosts).
# MAGIC_LINK_ORIGIN_ALLOWLIST=https://llmstxt.social,https://openorg.good-ship.co.uk
# From-address for Open Org login emails (Resend-verified domain required).
# OPENORG_FROM_EMAIL=Open Org <hello@openorg.good-ship.co.uk>
```

- [ ] **Step 2: Update the CORS example to include the openorg origin**

In `.env.example`, change the `CORS_ORIGINS` line to:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://llmstxt.social,https://openorg.good-ship.co.uk
```

- [ ] **Step 3: Commit**

```bash
git add .env.example CLAUDE.md
git commit -m "docs: document magic-link origin allowlist and openorg from-email"
```

---

### Task 6: Deploy runbook (manual + verified)

Operational task — run on the Mac Mini. No code; each step has a concrete check. **Stop and fix if any verification fails.**

- [ ] **Step 1 (USER): Verify the Resend sending domain**

In the Resend dashboard, verify `openorg.good-ship.co.uk` (or `good-ship.co.uk`) by adding the DKIM/SPF DNS records in Cloudflare. Verify status shows "Verified" before continuing. Until then, login emails 500.

- [ ] **Step 2 (USER): Add the Cloudflare Tunnel DNS route**

Run: `cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk`
(or add it in the Zero Trust UI). The Caddy block already exists.
Check: `dig +short openorg.good-ship.co.uk` resolves to the tunnel.

- [ ] **Step 3: Set prod env vars**

In the prod `.env` (Mac Mini): `RESEND_API_KEY`, `FROM_EMAIL`, `OPENORG_FROM_EMAIL`, `FRONTEND_URL=https://openorg.good-ship.co.uk` (fallback), `CORS_ORIGINS` includes both hosts, `AUTH_COOKIE_DOMAIN` **unset/commented**, `ENVIRONMENT=production`, LLM provider keys present.
Check: `grep -E 'AUTH_COOKIE_DOMAIN' .env` shows it commented or absent.

- [ ] **Step 4: Check out the branch and build the image**

```bash
git fetch && git checkout fix/openorg-hardening && git pull
docker compose build
```
Expected: build succeeds for the api/worker images (web `dist` baked in).

- [ ] **Step 5: Run migrations on the shared DB**

```bash
docker compose run --rm api alembic upgrade head
```
Expected: applies `org_signals` (and any pending) to head; no errors.

- [ ] **Step 6: Force-recreate the five services**

```bash
docker compose up -d --force-recreate api worker celery_worker beat celery_beat
```
Expected: all containers healthy (`docker compose ps`).

- [ ] **Step 7: Post-deploy smoke test (the definition of done)**

1. `https://openorg.good-ship.co.uk` loads with the **Open Org nav**.
2. Open the **Graph** view — renders, no "Something went wrong" (stale-bundle bug gone).
3. Request a magic link on openorg → an **Open Org-branded email** arrives → the link logs you in on `openorg.good-ship.co.uk`.
4. **Critical regression:** log in on `https://llmstxt.social` — its magic link still points to `llmstxt.social` and still works.

If step 4 fails, the Origin allowlist or cookie scope is wrong — investigate before declaring done.

---

## Self-Review

**Spec coverage:** Nav (already built — no task, confirmed via smoke step 7.1) ✓; request-aware magic link (Task 2) ✓; Open Org email branding (Task 3) ✓; security review (Task 4) ✓; commit WIP on branch (Task 1) ✓; env/CORS/cookie config (Task 5) ✓; tunnel route + Resend verify + build/migrate/recreate + smoke incl. llms.txt regression (Task 6) ✓. No gaps.

**Placeholder scan:** No TBD/TODO; all code steps show full code; commands have expected output. ✓

**Type consistency:** `_resolve_frontend_base(http_request)` defined in Task 2, used in Task 3's send block; `_email_branding(base_url)` defined and used in Task 3; `_allowed_origins()` used by `_resolve_frontend_base`. `send_magic_link` gains `http_request: Request | None = None` (keeps existing 2-arg test calls valid). Setting names `magic_link_origin_allowlist`, `openorg_from_email` consistent across config + usage + tests. ✓
