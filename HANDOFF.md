# Handoff — Phase 1 spec-complete; security blockers patched; ready for production rebuild

> Session ended: 2026-05-12
> Branch: `master` (post-merge of PR #16)
> Picks up from: spec-complete pass — analyzer enrichment, discovery surface (detail view + idea browser + about), blank templates, generate UI, history restore, Murmurations health-check, packaged Claude skills, security review with three blockers patched in
> Resumes at: production rebuild, post-claim redirect fix, or Phase 2 planning

## TL;DR

Nine PRs landed across the last two sessions, in order:

- **PR #6** (`99bfee2`) — Phase 1 + 1.5 + frontend polish: the Open Org sub-application, schema v0.2 prompt/crawler iteration, all baseline reports v0.1 → v0.4, CodeMirror editor, chat creator, strategy/idea editor pages, Vitest+RTL setup.
- **PR #7** (`86c7fbe`) — dev-mode magic-link logger + `LOCAL.md` walkthrough.
- **PR #8** (`32b2c4d`) — civic-editorial design pass on the Open Org SPA + four code-review fixes.
- **PR #9** (`bdda813`) — Chromium installed in the API/worker Docker image (so the v0.2.6 Playwright fallback fires in compose runs) + lazy-load `DiscoverPage` (fixes the prerender SSR break introduced by the Leaflet import).
- **PR #10** (`7022cb1`) — Rate limit + £0.50/org/day budget cap on `/api/open-org/generate`. The endpoint stays unauthenticated; two deterrents (per-IP 5/hour, per-org spend cap) sit in front of it.
- **PR #11** (`ec83c47`) — Daily `CreatorSession` eviction beat task + admin `POST /api/open-org/{org_id}/unpublish` route that flips `published=False` and dispatches a Murmurations node-delete task.
- **PR #12** (`0d0ae6b`) — Publish/Unpublish UI buttons on the profile editor, surfaced `published` on the GET profile.md response, fixed a pre-existing TZ bug in the daily-budget query window that was failing every `/api/open-org/generate` call against a real Postgres.
- **PR #14** (`0bb62f5`) — Publish/unpublish parity for strategies and ideas: 4 new admin routes, `published` flag on GET strategy.md/idea.md, badge + toggle on the strategy and idea editors, shared `PublishToggle` component used by all three editors. Closes a hidden Phase-1 gap where strategies/ideas had the column + the public-route gate but no API or UI to flip the flag — they were effectively un-publishable.
- **PR #16** (`ee6c88e`) — Phase-1 spec-complete pass. Wires `llmstxt_core.analyzer` into the profile generator (schema gains `mission.programmes` + `evidence_summary`; v0.5 baseline shows ~2× richer profiles). Adds rendered profile detail at `/openorg/{orgId}`, cross-org idea browser at `/openorg/ideas`, About page, blank-template "New strategy/idea" flows, public `/openorg/generate` form, non-destructive history restore + UI. Weekly Murmurations health-check task. Packaged `/org-strategy` + `/org-idea` Claude skills at `.claude/skills/`. Security review with three blocker patches included (forwarded-allow-ips, magic-link rate limit, CORS env-var documentation).

The v0.5 baseline scorecard (10 UK charities) is **6/6 must-pass green**, with substantially richer enrichment: programmes for 9/10, beneficiaries for 9/10, theory_of_change for 9/10, evidence_summary for 8/10, also_known_as for 7/10. Markdown length roughly doubled compared with v0.4. Click-through has been **executed** end-to-end on an isolated stack (generate → claim → publish → unpublish, JSON appears/disappears at the public URL, Murmurations submit/delete tasks fire).

## State at handoff

| Step | Status | Notes |
|------|--------|-------|
| 0 — Schemas + themes + validator | ✅ Done |
| 1 — Markdown ↔ JSON converter | ✅ Done |
| 2 — DB models + Alembic migration | ✅ Done | Head `c2d3e4f5a6b7` |
| 3 — CachedAnthropic + llm_usage | ✅ Done | `tools`/`tool_choice` support; TZ-naive window after PR #12 |
| 4 — Editor + magic-link admin auth | ✅ Done | CodeMirror 6 + preview + strategy/idea editor pages + Vitest+RTL + editorial design pass + publish/unpublish toggle (PR #12) |
| 5 — Profile generator | ✅ Done | Rate limit (5/IP/hour) + £0.50/org/day cap landed in PR #10 |
| 6 — Murmurations schema YAML | ✅ Drafted | **User opens upstream PR** |
| 7 — Murmurations connector | ✅ Done | Plus PR #11's unpublish + node-delete task |
| 8 — Strategy/idea chat creator | ✅ Done | Plus PR #11's daily CreatorSession eviction beat; publish/unpublish parity added in PR #14 |
| 9 — Discovery page | ✅ Done | `DiscoverPage` lazy-loaded as of PR #9 |
| 10 — Subdomain routing + Caddy | ✅ Done | `AUTH_COOKIE_DOMAIN` env-driven, Caddyfile updated, `HostRoot` redirect |
| 11 — Real-world testing harness | ✅ Done + baselined v0.1 → v0.4 |
| **Phase 1.5 — schema v0.2 iteration** | ✅ Done | v0.2.1 → v0.2.7, all 6/6 must-pass at v0.4 |
| **Editorial design pass** | ✅ Done | Civic-editorial type system + paper palette + per-page polish + four code-review fixes |
| **Operational hygiene** | ✅ Done | Chromium in worker image; per-IP + per-org caps on generate; eviction beat; unpublish + node-delete |
| **Publish/unpublish UI + click-through** | ✅ Done | PR #12 (profile) + PR #14 (strategy + idea parity) — all three record types now publishable from the SPA; profile flow validated end-to-end |
| **Phase-1 spec-complete pass** | ✅ Done | PR #16 — analyzer enrichment + schema v0.1.1 fields + profile detail view + idea browser + about page + blank templates + generate UI + history restore + Murmurations health-check + Claude skills + security review |

## v0.1 → v0.5 baseline scorecard

| Criterion | v0.1 | v0.2 | v0.3 | v0.4 | v0.5 |
|---|---|---|---|---|---|
| Trussell `food_access` | ❌ | ✅ | ✅ | ✅ | ✅ |
| Shelter `housing_and_homelessness` | ❌ | ❌ | ❌ | ✅ | ✅ |
| Mind `mental_health` | ❌ | ❌ | ✅ | ✅ | ✅ |
| NSPCC `children_and_young_people` | ❌ | ✅ | ✅ | ✅ | ✅ |
| Macmillan `families_and_carers` | ❌ | ✅ | ✅ | ✅ | ✅ |
| ≥3 orgs no spurious `education` | n/a | 6/7 | 5/7 | 6/7 | 6/7 |
| **v0.5 enrichment** — programmes populated | n/a | n/a | n/a | n/a | **9/10** |
| **v0.5 enrichment** — beneficiaries populated | n/a | n/a | n/a | n/a | **9/10** |
| **v0.5 enrichment** — theory_of_change populated | n/a | n/a | n/a | n/a | **9/10** |
| **v0.5 enrichment** — evidence_summary populated | n/a | n/a | n/a | n/a | **8/10** |

Reports committed at `tests/reports/baseline_v0.{1,2,3,4,5}.md`.

## Action items for the user

Pre-deploy:
1. **Open the Murmurations upstream PR** from `deploy/murmurations/` (schema name: `open_org_profile-v0.1.0`).
2. **Verify Resend domain** for `hello@openorg.good-ship.co.uk` (needed for prod magic-link + claim email deliverability).
3. **Rotate `ANTHROPIC_API_KEY` and `CHARITY_COMMISSION_API_KEY`** — both got printed into a chat transcript during the PR #12 click-through when a masking command failed. The keys are still functional; rotating is defence in depth.

Deploy:
4. **Set production env vars**:
   - `AUTH_COOKIE_DOMAIN=.good-ship.co.uk`
   - `MURMURATIONS_INDEX_URL` + `MURMURATIONS_LIBRARY_URL` — flip from test-index once the schema PR merges
   - `CORS_ORIGINS=https://llmstxt.social,https://openorg.good-ship.co.uk` — **required**, otherwise the SPA can't talk to the API from prod hosts (SECURITY-REVIEW.md M3)
5. **Add Cloudflare Tunnel route** for `openorg.good-ship.co.uk`:
   ```
   cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk
   ```
6. **Reload Caddy** with the new Caddyfile.
7. **Rebuild + force-recreate the api/worker containers** so production picks up everything PR #6+ added (the live api as of session-start was still serving a May-3 image without the open-org routes):
   ```
   docker compose build api worker
   docker compose up -d --force-recreate api worker
   ```
   Expect ~5 min for the Playwright `--with-deps` install during build.
8. **Note on the live Postgres**: open-org tables + claim-flow columns were applied during the PR #12 session (additive migrations, harmless on the still-stale image). They'll be needed as soon as you do the rebuild above.

## How to run things

**Backend tests** (in `python:3.11-slim`):
```bash
docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core[dev] -e "packages/api[dev]"
  cd packages/core && python -m pytest tests/ -q
  cd ../api && python -m pytest tests/ -q
'
```
Expected: 281 core + 170 api = **451 backend** green.

**Frontend**:
```bash
docker run --rm -v "$(pwd)/packages/web:/work" -w /work node:20-alpine sh -c '
  npm install --silent && npx tsc --noEmit && npm test
'
```
Expected: tsc clean, **31/31 vitest** green.

**Real-world harness** (Playwright is now in the worker image, but the harness still installs ad-hoc when run standalone):
```bash
docker run --rm --env-file .env -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core -e packages/cli > /dev/null
  playwright install --with-deps chromium > /tmp/pw.log 2>&1
  llmstxt openorg test-corpus
'
```
Cost: ~$0.15 for 10 charities. Writes to `tests/reports/real_world_run_<ts>.md` (git-ignored). Promote a vetted run to `tests/reports/baseline_v0.5.md` to update the reference.

**Local click-through**: see `LOCAL.md`. If the host's main docker-compose is already in use by a production deploy, an isolated test-stack pattern is what PR #12's click-through used — separate compose project name (`COMPOSE_PROJECT_NAME=llmstxt-test`), host ports `:8001` / `:5434` / `:6380`, and a thin `llmstxt-test-api` image (kept on disk for re-use) that extends `llmstxt-local-api` with the open-org python deps installed.

## Open follow-ups (no order, none block ship)

From the security review (SECURITY-REVIEW.md):
- **M1** — design decision on whether to verify `owner_email` against the CC-registered email before sending claim links. Currently first-come-first-served — anyone who knows a charity number can race to claim ownership. Phase-1 design choice per spec; revisit before broad public launch.
- **M2** — audit which subdomains under `good-ship.co.uk` should receive the auth cookie. `AUTH_COOKIE_DOMAIN=.good-ship.co.uk` sends the cookie to every subdomain; if `ghost.good-ship.co.uk` / `soundings.good-ship.co.uk` / others are also under that suffix, they receive the auth token.
- **L1–L7** — defence-in-depth hardening: HSTS at Caddy, CSP header, JWT secret-key strength documentation, content-sniffing on uploads, TZ-naive comparison in auth (same class as PR #12's fix), Murmurations URL pinning, 409 existence-leak softening.

From prior sessions, still open:
- **Post-claim redirect honours `org_id`**. `/auth/verify` returns JSON and the frontend post-auth landing is hardcoded to `/dashboard`. After a claim flow the user should land at `/openorg/edit/{org_id}/profile`. Backend has the `org_id` on the magic-link token; needs (a) the verify response to surface it and (b) the frontend Verify page to use it.
- **`GET /api/open-org/areas` typeahead** for the discovery area-code filter (~30 min).
- **Diff-vs-baseline mode for the harness** — `llmstxt openorg compare baseline_v0.5.md` (~45 min).
- **Live ONS centroid coverage** beyond UK nations + major cities; `refresh_from_ons` CLI hook (~1h).
- **Postgres integration tests for JSONB filter paths** — needs a test-container fixture (~1.5h). Would also catch the class of bug PR #12 fixed (asyncpg TZ comparison) — that's only visible against a real Postgres.
- **API tenant gating per host** (deliberately deferred — revisit when real logs show traffic on the wrong host).
- **Firecrawl as a third fetch tier** (only if a future corpus surfaces sites that defeat both httpx and Playwright).
- **Lower-scored design-pass items from the code review**: result-card `<h2>` semantics, file-input focus indicator, form-input focus ring beyond the 1px border, link underlines at rest on the Discover org name.
- **`react-hooks/rules-of-hooks` violations** on `Create.tsx` and parts of `Discover.tsx` (still pre-existing — PR #12, #14, #16 cleaned up everything they touched).
- **Analyzer token usage not reported by the harness** — `analyze_organisation` instantiates its own SDK client and doesn't return usage, so the harness's per-charity token totals undercount real spend by ~2-3×. Cosmetic; cost cap is still enforced at the budget service which sees logged usage.

Items that landed across the last two sessions (strikes from the prior follow-ups list):
- ~~Chromium in the `celery_worker` Docker image~~ → PR #9
- ~~Rate limiting + £0.50/org/day cap on `/api/open-org/generate`~~ → PR #10
- ~~Daily Celery beat to evict expired `CreatorSession` rows~~ → PR #11
- ~~Murmurations node deletion when an OrgProfile is unpublished~~ → PR #11
- ~~Publish/unpublish UI buttons in the SPA~~ → PR #12 (profile) + PR #14 (strategy + idea)
- ~~Local click-through executed end-to-end~~ → PR #12 session
- ~~Strategy/idea publish parity (hidden Phase-1 gap)~~ → PR #14
- ~~Profile fills as much as possible from the initial crawl and API pull~~ → PR #16 (analyzer wired in, programmes + beneficiaries + evidence_summary)
- ~~Profile detail view at `/openorg/{orgId}` (rendered, not raw JSON)~~ → PR #16
- ~~Idea browser at `/openorg/ideas`~~ → PR #16
- ~~About page at `/openorg/about`~~ → PR #16
- ~~Blank "New strategy" / "New idea" templates with HTML-comment guidance~~ → PR #16
- ~~Frontend Generate Profile UI~~ → PR #16
- ~~History restore endpoint + UI~~ → PR #16
- ~~Weekly Murmurations health-check task~~ → PR #16
- ~~Package `/org-strategy` and `/org-idea` as installable Claude skills~~ → PR #16
- ~~Run `/security-review` on the five deliverables~~ → PR #16 (SECURITY-REVIEW.md)
- ~~Rate-limit middleware honours real client IP behind reverse proxy~~ → PR #16 (H1)
- ~~`/api/auth/magic-link` rate-limited~~ → PR #16 (H2)
- ~~`CORS_ORIGINS` documented as a required production env var~~ → PR #16 (M3)

## Notable decisions this session

PR #16 (spec-complete pass):
- **Schema additions are additive — no v0.2 bump.** `mission.programmes` and `mission.evidence_summary` are optional fields on `open-org/v0.1`. Existing profiles validate unchanged. Hypercerts is documented in the `evidence_summary` description as the planned Phase-4 extension for richer evidence linking.
- **Single crawl, multiple consumers.** `collect_website_pages` is the new core function; `collect_website_text` is a thin wrapper. The generator calls the crawl once and feeds both the theme extractor (text) and the analyzer (pages) — no duplicate HTTP.
- **CC is the spine, analyzer fills soft tissue.** CC contact wins where present; analyzer fills gaps (email/phone/address). Analyzer geography wins only when CC's value is vague ("England", "United Kingdom"). Working name only added to `also_known_as` when distinct from CC registered name.
- **Analyzer failures degrade gracefully.** A flaky analyzer (network, parse error) returns no enrichment but CC-only profile generation still succeeds.
- **Cross-org idea browser is a separate endpoint** (`/api/open-org/discover/ideas`) rather than overloading the existing org-discovery endpoint. Different result shape (idea-centric, with cost range) justifies the split.
- **History restore is non-destructive.** Restoring a past version appends a new version pointing to the chosen snapshot; old versions stay in place. Schema validation runs against the snapshot, so if v0.2 ever tightens a constraint and an old snapshot becomes invalid, restore returns 400 with structured field errors rather than silently writing bad data.
- **Murmurations health check** is weekly (Mondays 04:00 UTC) — schema drift is rare and validating every published profile against the live library schema is mildly expensive. Recovers automatically: a profile that flips to `drift` then validates clean on the next run flips back to `validated`.
- **Three security blockers fixed in this PR** so the production rebuild can proceed without queueing a follow-up PR first.

PR #12 (publish/unpublish + TZ fix):
- Extended `MarkdownResponse` with `published: bool` rather than adding a new state endpoint — backwards-compatible (older clients ignore the field) and saves a round-trip.
- A single toggle button (Publish ↔ Unpublish) rather than two coexisting buttons, gated on `profile.data.published`. Keeps the header uncluttered. Inline alert handles the "save markdown before publishing" 400 path.
- TZ-naive window in `_today_window_utc` is correct for the *current* column type (`TIMESTAMP WITHOUT TIME ZONE`). The "right" long-term fix is migrating to `TIMESTAMPTZ`, but that's a separate migration with bigger blast radius — current fix unblocks generate without any data-layer changes.
- Regression test asserts the function returns naive datetimes. Doesn't replace the need for a real-Postgres integration test (still on the follow-ups list), but does encode the contract.

Click-through methodology (worth keeping for next time):
- Isolated test stack (`COMPOSE_PROJECT_NAME=llmstxt-test`, ports `:8001` / `:5434` / `:6380`, named volume) with a fresh DB per run — production data untouched, teardown is `docker compose -p llmstxt-test down -v`. The `llmstxt-test-api` extension image is kept on disk between runs.

## Files of note

PR #16 (spec-complete pass — 40 files, +4546/-99):
- `packages/core/src/llmstxt_core/open_org/schemas/org_profile.schema.json` — `mission.programmes` + `mission.evidence_summary` (additive).
- `packages/core/src/llmstxt_core/open_org/generator.py` — analyzer wired in via `_build_payload(analysis=...)`; merge helpers (`_merge_programmes`, `_evidence_summary`, vague-area override).
- `packages/core/src/llmstxt_core/open_org/website_text.py` — refactored to expose `collect_website_pages`; `collect_website_text` is now a wrapper.
- `packages/core/src/llmstxt_core/open_org/harness.py` — richer per-charity report (programme names, beneficiaries, enrichment flags).
- `tests/reports/baseline_v0.5.md` — v0.5 corpus run report.
- `packages/api/src/llmstxt_api/routes/open_org_public.py` — new `GET /open-org/{org_id}/{strategies,ideas}` list endpoints feeding the profile detail page.
- `packages/api/src/llmstxt_api/routes/open_org_discovery.py` — new `GET /api/open-org/discover/ideas` cross-org idea endpoint.
- `packages/api/src/llmstxt_api/routes/open_org_admin.py` — `POST .../history/{version_id}/restore` (non-destructive).
- `packages/api/src/llmstxt_api/tasks/open_org_murmurations.py` — `_run_health_check` + `health_check_murmurations_task` (Mondays 04:00 UTC beat).
- `packages/api/src/llmstxt_api/middleware/rate_limit.py` — new rule for `/api/auth/magic-link` (H2); `print` → `log.error` (M4).
- `packages/api/src/llmstxt_api/config.py` — `magic_link_hourly_limit` setting.
- `packages/api/Dockerfile` + `docker-compose.yml` — `--forwarded-allow-ips=127.0.0.1` on uvicorn (H1).
- `packages/web/src/pages/openorg/ProfileDetail.tsx` — rendered profile detail view at `/openorg/{orgId}`.
- `packages/web/src/pages/openorg/Ideas.tsx` — cross-org idea browser at `/openorg/ideas`.
- `packages/web/src/pages/openorg/About.tsx` — explainer page.
- `packages/web/src/pages/openorg/NewRecord.tsx` + `packages/web/src/openorgTemplates.ts` — blank-template "New strategy" / "New idea" flows.
- `packages/web/src/pages/openorg/Generate.tsx` — public form to kick off profile generation.
- `packages/web/src/pages/openorg/EditProfile.tsx` — `HistoryPanel` + chat/template create entry-point buttons.
- `.claude/skills/org-strategy/SKILL.md` + `.claude/skills/org-idea/SKILL.md` — installable Claude skills (per spec section 2.5).
- `SECURITY-REVIEW.md` — `/security-review` skill output + per-finding fixes.

PR #14 (strategy/idea publish parity):
- `packages/api/src/llmstxt_api/routes/open_org_admin.py` — 4 new routes (`publish_strategy`, `unpublish_strategy`, `publish_idea`, `unpublish_idea`) + `RecordPublishResponse` schema + `published` on the GET strategy.md / idea.md responses.
- `packages/api/tests/test_open_org_record_publish_route.py` — 11 tests for the new routes + the GET flag.
- `packages/web/src/api/openorg.ts` — `publishStrategy` / `unpublishStrategy` / `publishIdea` / `unpublishIdea` + matching `use*` hooks.
- `packages/web/src/components/openorg/PublishToggle.tsx` — shared `PublishBadge` + `PublishControls` used by all three editors.
- `packages/web/src/pages/openorg/EditStrategy.tsx`, `EditIdea.tsx` — badge + toggle + inline alert, hooks lifted above early-return.
- `packages/web/src/pages/openorg/{EditStrategy,EditIdea}.test.tsx` — 4 Vitest tests each, mirroring the profile test pattern.

PR #12 (profile publish + TZ fix):
- `packages/api/src/llmstxt_api/routes/open_org_admin.py` — `MarkdownResponse.published`; GET handler populates it from `profile.published`.
- `packages/api/src/llmstxt_api/services/llm_usage.py` — `_today_window_utc` returns naive UTC datetimes.
- `packages/api/tests/test_open_org_admin_routes.py` — new test for the `published` field.
- `packages/api/tests/test_llm_usage_service.py` — regression test for the naive-window contract.
- `packages/web/src/api/openorg.ts` — `publishProfile` / `unpublishProfile` + `usePublishProfile` / `useUnpublishProfile` hooks + `OpenOrgPublishError`.
- `packages/web/src/pages/openorg/EditProfile.tsx` — Draft/Published badge, single toggle button, inline alert, hooks lifted above early-return (refactored to use the shared `PublishToggle` in PR #14).
- `packages/web/src/pages/openorg/EditProfile.test.tsx` — 4 Vitest+RTL tests for the toggle.

Earlier this Phase (still relevant context):
- `packages/core/src/llmstxt_core/playwright_fetch.py` — Playwright wrapper (PR #6, used by website crawl fallback).
- `packages/core/src/llmstxt_core/open_org/website_text.py` — two-tier crawl orchestrator with URL normalisation + homepage-by-URL override.
- `packages/web/src/pages/openorg/{Discover,Create,EditProfile,EditStrategy,EditIdea}.tsx` + `components/openorg/MarkdownEditor.tsx` — editorial redesign.
- `packages/api/Dockerfile` — Chromium install (PR #9).
- `packages/web/src/App.tsx` — lazy DiscoverPage (PR #9).
- `packages/api/src/llmstxt_api/middleware/rate_limit.py` + `config.py` — per-IP hourly cap (PR #10).
- `packages/api/src/llmstxt_api/routes/open_org_generate.py` — budget gate (PR #10).
- `packages/api/src/llmstxt_api/tasks/open_org_creator.py` — eviction task + beat schedule entry (PR #11).
- `packages/api/src/llmstxt_api/tasks/open_org_murmurations.py` — `_run_node_delete` + `delete_from_murmurations_task` (PR #11).
- `packages/api/src/llmstxt_api/routes/open_org_admin.py` — `POST .../unpublish` route (PR #11), publish/unpublish response models extended (PR #12).

## How to resume

After `cd /Users/tomcwxyz/llmstxt-local`:

```
Read CLAUDE.md, then PLAN.md, then HANDOFF.md, then SECURITY-REVIEW.md.
Phase 1 is spec-complete and security-reviewed; three blocker patches
are in. Status check + propose next focus.
```

Most natural next picks:
- **Production rebuild + DNS** — `docker compose build` + `up -d --force-recreate api worker` so the live deploy picks up everything from PR #6 through PR #16, then add the Cloudflare Tunnel route to `openorg.good-ship.co.uk`. The live image at session-start was still May-3 and predates all open-org code.
- **Post-claim redirect fix** so the verify flow lands directly on the profile editor when the magic-link token carries an `org_id`. ~30 min.
- **Subdomain cookie audit (SECURITY-REVIEW.md M2)** — confirm every `*.good-ship.co.uk` subdomain that will receive the auth cookie is a trusted service. Ghost / Soundings run on the same host; if any are reachable under that root they receive `auth_token` on every request.
- **Phase 2 planning** (access control + grants, MCP integrations, funder profiles, strategy matching).
