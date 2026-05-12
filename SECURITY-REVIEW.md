# Security review — Open Org Phase 1 + 1.5 + spec-complete

> Run: 2026-05-12, on branch `feat/openorg-spec-complete`
> Scope: profile generator, strategy/idea creator, markdown editor, Murmurations connector, discovery page (including new profile detail view, idea browser, history restore, blank templates, Generate UI from this PR).
> Reviewer: project-level `/security-review` skill, per spec section 11 checklist.

## TL;DR

**Nothing critical. Two high-severity issues should be fixed before the production rebuild lands** — they're both small, well-scoped changes that affect every authenticated/rate-limited endpoint. The rest is a mix of medium configuration hygiene and low-severity hardening worth tracking but not blocking.

## Findings by severity

### Critical
None.

### High

#### H1. Rate limiting is broken behind Caddy / Cloudflare Tunnel

**Where:** `packages/api/src/llmstxt_api/middleware/rate_limit.py:52` and the uvicorn command in `docker-compose.yml`.

**What:** The middleware keys its bucket on `request.client.host`. Behind a reverse proxy, Starlette/uvicorn will report the proxy's source IP (127.0.0.1 when Caddy is colocated) unless explicitly told to honor `X-Forwarded-For`. The deploy uses Cloudflare Tunnel → Caddy → uvicorn but nothing in the stack is configured to forward the real client IP into FastAPI.

**Why it matters:** Every request to `/api/open-org/generate` (and any future rate-limited path) shares one bucket keyed on `127.0.0.1`. The 5/hour cap is a server-wide cap, not a per-IP one. An attacker triggers all 5 generations within a minute and locks out every other legitimate visitor for an hour. The intended deterrent is gone.

**Fix:** Add `--forwarded-allow-ips=127.0.0.1` to the uvicorn command (it accepts `*` if you want to trust all upstream proxies, but be specific):

```yaml
# docker-compose.yml — api service
command: uvicorn llmstxt_api.main:app --host 0.0.0.0 --port 8000 --reload --forwarded-allow-ips=127.0.0.1
```

Or, in `main.py`, add Starlette's `ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")` before `RateLimitMiddleware`.

Then add a regression test that calls the middleware with `request.client.host="127.0.0.1"` plus `X-Forwarded-For: 203.0.113.7` and asserts the bucket key reflects `203.0.113.7`.

---

#### H2. `/api/auth/magic-link` is unauthenticated and unthrottled — email-bomb vector

**Where:** `packages/api/src/llmstxt_api/routes/auth.py:90`. The endpoint has no rule in `middleware/rate_limit.py::_rule_for`.

**What:** Anyone can POST `{ "email": "<target>@example.com" }` and the server will send a styled Resend email containing a real (single-use, 15-min) login link. The endpoint deletes prior unused tokens for the same email per call, so it can't be used to accumulate tokens — but each call still triggers a real email send.

**Why it matters:**
- **Email-bomb:** an attacker spams a target inbox with login emails from a verified Resend sender. Mailbox annoyance is the obvious harm; reputation damage to the Resend domain (recipients reporting as spam) is the more durable one.
- **Cost:** each send hits Resend. Cheap but not free; abuse at scale matters.
- **Phishing surface:** a flood of real "log in to llms.txt" emails increases the chance the target clicks one of the attacker's separate phishing emails styled to look the same.

**Fix:** Add a rule to `_rule_for(path)`:

```python
if path.startswith("/api/auth/magic-link"):
    return (
        "rate_limit:magic_link",
        5,  # 5 requests per IP per hour — generous for fat-finger retries
        3600,
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"),
    )
```

After H1 is fixed (so the IP keying actually works). Consider also rate-limiting per `email` value, not just IP, so a rotating-IP attacker still can't bomb one address.

---

### Medium

#### M1. First-come-first-served claim on `/api/open-org/generate`

**Where:** `packages/api/src/llmstxt_api/routes/open_org_generate.py:60` → `tasks/open_org_generate.py` → claim email.

**What:** The request body carries `owner_email`. The Celery task generates the profile then sends the claim link to whatever address was submitted. Whoever clicks the link becomes `OrgAdmin(role="owner")` via `routes/auth.py:226`. There's no verification that the submitter is affiliated with the charity.

**Why it matters:** An attacker who knows a charity's number can race the legitimate organisation to claim ownership. After clicking the link, they have edit + publish authority on a profile that purports to represent that charity. The federated index would carry their version. This is a Phase-1 design choice per spec section 1 ("magic link sent to email they entered"), not a flaw in the implementation — but it's worth surfacing before public launch.

**Fix options (any one works):**
- **Verify against CC's registered email** (`cc.contact.email`). Reject `owner_email` if it doesn't match the email Charity Commission has on file for that charity. Stricter but cleanest.
- **Notify the CC-registered email when a claim is started by a different address.** Out-of-band confirmation, weaker but doesn't block legitimate orgs whose CC contact is stale.
- **Manual review queue.** Generated profiles park in a `pending_review` state; an admin (you) approves the email-charity binding before the claim link is sent. Highest friction.

For Phase 1 with low traffic, M1 + a short HANDOFF note is probably enough; revisit when public.

---

#### M2. Auth cookie domain `.good-ship.co.uk` shares the cookie with every subdomain

**Where:** `packages/api/src/llmstxt_api/config.py:39` (`auth_cookie_domain`), `routes/auth.py:252` (cookie set), `Caddyfile`.

**What:** Production `AUTH_COOKIE_DOMAIN=.good-ship.co.uk` (locked decision #9) intentionally scopes the cookie to span `llmstxt.social` and `openorg.good-ship.co.uk`. A leading-dot value also sends it to `ghost.good-ship.co.uk`, `soundings.good-ship.co.uk`, and any other subdomain under that suffix.

**Why it matters:** The Mac Mini already runs other services (Ghost CMS, Soundings, observed via `docker ps`). If any of them is reachable at a `*.good-ship.co.uk` host, the user's auth_token will be sent there too on every request. A compromise of any subdomain service — XSS, request-logging bug — exposes the auth token.

**Fix:**
- Audit which subdomains exist under good-ship.co.uk and confirm each is trusted to receive the cookie.
- If not, switch cookie domain to a specific `Domain=openorg.good-ship.co.uk` (loses the cross-subdomain SSO) and serve the SPA from the same host as the API for llmstxt-social too.
- Or run the SSO-scoped subdomains under a dedicated suffix (`.app.good-ship.co.uk`) and limit the cookie there.

---

#### M3. CORS allowlist defaults to localhost

**Where:** `packages/api/src/llmstxt_api/config.py:60` — `cors_origins: str = "http://localhost:3000,http://localhost:5173"`.

**What:** With `allow_credentials=True` + a specific allowlist, this is correctly safe in development. But the default values only cover dev hosts. If `CORS_ORIGINS` isn't explicitly set in production env vars, browsers will refuse credentialed requests from `https://openorg.good-ship.co.uk` to the API.

**Why it matters:** Functional break, not a vuln — but it'll silently take the SPA offline if missed. Worth a deploy-time check.

**Fix:** Add to HANDOFF "Action items for the user" a line:
```
CORS_ORIGINS=https://llmstxt.social,https://openorg.good-ship.co.uk
```
And keep `allow_credentials=True` — it's already correctly gated by a specific allowlist (no `*`).

---

#### M4. Rate-limit middleware fails open when Redis is down

**Where:** `packages/api/src/llmstxt_api/middleware/rate_limit.py:81` — `except Exception: ... return await call_next(request)`.

**What:** If Redis is unreachable, the middleware logs and allows the request through. This is a deliberate availability trade-off, but it means Redis being briefly down opens the generate endpoint to unbounded use, and the only loss-of-Redis signal is a printed line on stdout.

**Why it matters:** Combines badly with H1 — until H1 is fixed, a Redis hiccup is hard to distinguish from successful rate-limiting (since the limit was server-wide anyway). After H1 is fixed, Redis downtime is a real failure mode worth alerting on.

**Fix:** Replace `print(...)` with `log.error(...)` so it lands in a log aggregator instead of being swallowed by the container's stdout. Consider also emitting a Prometheus-style counter if/when you wire metrics in.

---

### Low / informational

#### L1. JWT signing requires `SECRET_KEY` ≥ 32 random bytes

**Where:** `config.py:31` — `secret_key: str` (required, no default).

`Settings` correctly forces the env var to be set (no default), so an empty/missing key fails at startup. The remaining risk is a weak human-chosen value. Worth a deploy note that this must be high-entropy random.

#### L2. Existence leak via 409 on `/api/open-org/generate`

The 409 response distinguishes "charity already has a profile in our system" from "no profile yet". Charity numbers are public; what's new is whether we've enumerated it. Low impact. Mitigation if you cared: always return 202 and de-duplicate inside the worker.

#### L3. TZ-naive vs TZ-aware in auth's `expires_at < datetime.utcnow()`

`packages/api/src/llmstxt_api/routes/auth.py:203` does the same naive comparison the daily-budget query did before PR #12's fix. Currently safe because `expires_at` is TZ-naive at the column level too — but a future migration to `TIMESTAMPTZ` would trip it. Either add the same regression test contract or migrate both at once.

#### L4. HSTS header not set at Caddy

`deploy/caddy/Caddyfile` sets X-Frame-Options, X-Content-Type-Options, etc., but no `Strict-Transport-Security`. Cloudflare typically sets HSTS at the edge, but defence in depth is cheap. Add:

```
Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
```

…to both site blocks. Make sure preload is what you want before enabling.

#### L5. No Content-Security-Policy

Neither Caddy nor FastAPI sets a CSP header. Setting even a permissive baseline (e.g. `default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'`) limits the blast radius of a dependency compromise. Worth doing alongside the SPA's existing inline styles.

#### L6. Document uploads dispatched by file extension only

`packages/core/src/llmstxt_core/open_org/creator/extractors.py:43` keys the dispatch on filename extension, not content sniffing. Each handler (`pypdf`, `python-docx`, UTF-8 decode) defensively wraps the parse, and the 10 MB cap is enforced — so the failure modes are graceful exceptions, not exploits. Low risk, but worth tracking if more formats are added.

#### L7. Murmurations index URL is operator-controlled — pin in prod

Configured via env vars. Defaults to test-index. Once the upstream schema PR merges and the production index is enabled, make sure those env vars are pinned and not accidentally rolled back to test (which would silently invalidate every prior submission).

---

## What was specifically checked, no findings

- **Anthropic API key handling.** Read from env in `config.py:18`, passed into `CachedAnthropic` and `analyze_organisation`. Never returned in any response, never logged. The analyzer instantiates its own Anthropic client with `os.getenv("ANTHROPIC_API_KEY")` as fallback — make sure the worker env always has this set (it does in compose).
- **Magic-link token handling.** 32-byte `secrets.token_urlsafe`, 15-min TTL for login, 24h TTL for claim. Stored as the raw token in the DB (so DB compromise = token compromise — acceptable trade-off for short TTL). Single-use via `used=True`. Prior unused tokens deleted on re-request.
- **Profile data validation.** Every PUT runs `markdown_to_json → validate_for_kind` before persisting. ConverterError + ValidationError both surface as 400 with structured field errors. History restore re-runs the validator against the snapshot (good).
- **Murmurations submission.** Validates against the test/prod library before submitting. Retries on `MurmurationsError` (5xx). Node-delete fires only when `murmurations_node_id` is set. Daily cache sync deletes stale rows but only those whose org_ids aren't in the latest pull. Health-check task (PR D1) re-validates published profiles weekly.
- **SQL injection.** All queries use SQLAlchemy ORM + parameter binding. JSONB filters use the `?` operator which binds the value, and `ilike(like)` binds the pattern. No string concatenation observed in any query.
- **IDOR on edit routes.** `require_org_admin(org_id)` is the gate; the `org_id` comes from the URL and is compared against the user's OrgAdmin grants. History restore additionally filters versions by `parent_id=profile.id` so a user can't restore a version belonging to a different org even if they guess the UUID.
- **Existence leak on public profile routes.** Unpublished profiles return 404 (not 403) so the public can't tell a missing org from a draft. Same for strategies, ideas, and the murmurations envelope.
- **Directory traversal on SPA fallback.** `main.py::resolve_web_path` correctly enforces that resolved paths stay inside `web_dist_dir`.
- **Document upload size cap.** 10 MB enforced in `extractors.py:38` before any parse attempt.

---

## Recommended fixes before production rebuild

Block on these:

1. **H1** — add `--forwarded-allow-ips=127.0.0.1` to uvicorn. Without it the rate limit is broken in production.
2. **H2** — add `/api/auth/magic-link` to the rate-limit rules. Without it the magic-link endpoint is an email-bomb tool.
3. **M3** — make sure `CORS_ORIGINS` is set in production env, otherwise the SPA breaks at the API boundary.

Address as part of the next polish pass:

4. **M1** — design decision on whether to verify owner_email against CC's registered email before sending claim links.
5. **M2** — audit which subdomains under good-ship.co.uk receive the auth cookie.

The rest (M4, L1-L7) are good-to-have hardening worth tracking but not gating launch.

---

## Status — patched in this PR

The three pre-launch blockers above (and one of the mediums) were patched onto `feat/openorg-spec-complete` after this review was written:

- ✅ **H1** — `--forwarded-allow-ips=127.0.0.1` added to the uvicorn command in `docker-compose.yml:54` and the `CMD` in `packages/api/Dockerfile:67`. Rate-limit middleware now sees real client IPs once production rebuild lands.
- ✅ **H2** — new rule in `middleware/rate_limit.py::_rule_for` keyed on `/api/auth/magic-link`. Default cap: 5/hour/IP via the new `magic_link_hourly_limit` setting. Regression test in `tests/test_rate_limit_rules.py` pins the contract so a future change can't silently drop it.
- ✅ **M3** — added `CORS_ORIGINS` to the HANDOFF "Action items for the user" production env block.
- ✅ **M4 (partial)** — replaced the `print(...)` fail-open log with `log.error(...)` so Redis outages land in the log aggregator.

Still open: **M1**, **M2**, **L1–L7**. None block launch.
