# Handoff — Editor-polish PR 5 + PR 6 complete; PR 7 is all that remains

> Session ended: 2026-06-05
> Branch: `editor-polish-pr5-generate` (name is historical — it now carries **PR 1 through PR 6**, all stacked)
> Picks up from: the editor-polish plan (`docs/superpowers/plans/2026-05-19-openorg-editor-polish.md`)
> Resumes at: **PR 7 — Keyboard + motion polish (tasks 7.1–7.2)**, the final PR; or push/PR the stack

## TL;DR

This session resumed mid-PR-5 (task 5.4 was already committed). Completed the rest of **PR 5** (live Generate progress) and all of **PR 6** (claim redirect + WelcomeStrip + microcopy). Both PRs are green. Along the way, fixed two pre-existing breakages the earlier PRs had left on the branch.

- **PR 5 (5.5–5.8)** — `lookupCharity` + `useGenerateStatus` client hooks; `GenerateLiveStatus` component; `Generate.tsx` wired to inline charity-name lookup + live status polling; PR gate green.
- **PR 6 (6.1–6.5)** — `claim_org_id` on `AuthResponse` + verify endpoint; post-claim verify redirects to `/openorg/edit/{orgId}/profile` and sets the `openorg.welcomeStrip.{orgId}=pending` flag; `WelcomeStrip` one-time strip; WelcomeStrip + "Start here" wired into `EditProfile`; `microcopy.ts` central string module with a sweep across 6 components.

## Two pre-existing fixes made to unblock the PR-5 gate

1. **`fix(web): restore green tsc build` (`6d27286`)** — PRs 2–4 left `tsc`/`npm run build` RED (it had gone unnoticed because backend-only tasks 5.1–5.4 never re-ran the JS gate). Causes: `tsconfig` targeted ES2020 but tests use `Array.at()` (→ bumped target+lib to **ES2022**, user-approved); `beforeEach(() => vi.useFakeTimers())` arrows leaked vi's return type (→ block bodies); `Section.tsx` pill `options` leaked an empty-string case past `?? []`; an untyped `vi.fn()` mock in `EditorShell.test.tsx`.
2. **`test(openorg): cover new generation status columns` (`f94d1ca`)** — task 5.1 added 5 columns to `OrgProfile` (`generation_stage/message/payload/started_at/finished_at`) but didn't update the structural test `test_org_profile_columns`.

## Microcopy sweep — one intentional trade-off to know about

The 6.5 sweep flattens two micro-details into plain strings (the plan specifies `t(...)` calls for both): the publish-confirm URL is no longer wrapped in `<code>`, and `⌘S` in the "Unsaved" hint is no longer in a mono `<span>`. Tests stay green and visible text is unchanged. Restore the styling later if desired (keep the JSX structure, source only the words from microcopy).

## State at handoff

- Branch `editor-polish-pr5-generate` is **45 commits ahead of `master`** — all of PR 1–6 stacked on one branch (the per-PR-branch plan was never followed; the original git-auth block meant nothing was ever pushed/merged).
- **`gh` auth now WORKS** (`dataforaction-tom`) — the earlier block is cleared. Nothing pushed yet **by user choice** this session.
- All gates green: web `tsc` clean · `npm run lint` exit 0 · **119 vitest pass (31 files)** · `npm run build` exit 0. Backend: **281 core + 179 api = 460 pass** (run via `/Users/tomcwxyz/llmstxt-local/.venv` — Python 3.11, both packages installed).
- Working tree: this HANDOFF.md edit + `.superpowers/` (untracked) are the only non-committed items.

## How to resume

Option A — **finish the plan (PR 7)**: tasks 7.1 (Cmd/Ctrl+S save on both surfaces; `j`/`k` section nav + Enter-to-focus in `GuidedEditor`) and 7.2 (`motion.ts` timing constants + `prefers-reduced-motion` audit). Plan has exact tests + code at lines ~5817–6076. Note 7.2 Step 4 is a **manual browser reduced-motion smoke check** — can't run headlessly.

Option B — **push the stack**: `git push -u origin editor-polish-pr5-generate`, open ONE PR to `master` bundling PR 1–6 (call out the bundling + the two fix commits `6d27286`/`f94d1ca` in the body). Then optionally do PR 7 as a follow-up off the updated master.

## Verification commands

```bash
cd packages/web && npx tsc --noEmit && npx vitest run && npm run lint && npm run build
# backend (Python 3.11 venv already set up):
cd packages/api  && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/ -q   # 179
cd packages/core && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/ -q   # 281
```

(The `npm run build` tail line "build was canceled / Vite server closed" is a cosmetic prerender-server shutdown artifact — exit code is 0; the sitemap step runs after it and succeeds.)

---

> NOTE: everything below is the PRIOR PR-1 handoff (2026-06-01) and the Phase-1 handoff (2026-05-12). Kept for historical context.

---

# Handoff — Editor-polish PR 1 verified + lint debt cleared; BLOCKED on git auth

> Session ended: 2026-06-01
> Branch: `editor-polish-pr1-bridge` (off `master`)
> Picks up from: the editor-polish plan (`docs/superpowers/plans/2026-05-19-openorg-editor-polish.md`) — PR 1 of 7
> Resumes at: push + open PR + merge PR 1 (blocked on auth), then PR 2 (Field components)

## TL;DR

PR 1 of the 7-PR editor-polish plan (a dual-surface Guided + Markdown editor for the four Open Org flows) was already implemented on `editor-polish-pr1-bridge` before this session (commits `8edeb2c`..`dc778c8`): `bridge.ts` (per-section markdown splicer) + three section-spec files (`profile.ts`/`strategy.ts`/`idea.ts`) + `js-yaml` dep. No UI yet — this is the contract the Guided editor (PRs 2–4) is built on.

This session:
1. **Verified PR 1 green** — `tsc` clean, 22 guided tests (53 total) pass, `npm run build` exits 0.
2. **Cleared pre-existing lint debt** so `npm run lint` (which runs `--max-warnings 0`) passes — it was red from 17 errors + 10 warnings predating this branch, which would block any CI keyed on the lint gate. Commit **`1fee161`** `fix(web): clear pre-existing eslint failures across web package`.

## State at handoff

- Branch `editor-polish-pr1-bridge` = PR 1 feature work + commit `1fee161` (lint cleanup) on top.
- All gates green: `tsc` clean · 53/53 vitest · `npm run lint` exit 0 · `npm run build` exit 0.
- **Nothing pushed. No PR. Not merged.** Both auth paths are down:
  - SSH push → `Permission denied (publickey)`
  - `gh` → token invalid (`gh auth status` fails)
- **No backend changes this branch** (`api`/`core`/`cli` untouched) → no migration/deploy risk.
- New `guided/` modules + `js-yaml` are imported by **nothing in the app** → tree-shaken out of the production bundle → zero runtime impact on either host. llmstxt-social renders identically.

## On commit `1fee161` (the lint cleanup) — call this out in the PR description

It touches 9 existing files, 6 of which are on the **shared llmstxt-social path**: `App.tsx`, `AuthContext.tsx`, `PaymentFlow.tsx`, `SubscriptionFlow.tsx`, `pages/Generate.tsx`, `SchemaScript.tsx` (the other 3 are openorg-only: `openorg.ts`, `MarkdownEditor.tsx`, `Create.tsx`). All changes are **behavior-preserving**:
- `Create.tsx` — real `react-hooks/rules-of-hooks` bug fixed: 9 `useState` + `useRef` + `useEffect` were running *after* an early return; hoisted all hooks above the URL guard.
- `AuthContext`/`openorg.ts`/`MarkdownEditor` — `any` → `unknown`/precise types.
- `openorg.ts` — `while (true)` SSE reader → flagged loop.
- `SubscriptionFlow` — static caption was a `<label>` with no control → `<div>`.
- `Generate.tsx` — radiogroup made focusable (`tabIndex`).
- `PaymentFlow` — depend on the stable `mutate` ref (avoids the render loop that adding the whole mutation object would cause).
- `App`/`SchemaScript`/`AuthContext` — targeted `eslint-disable` for the HMR-only `react-refresh/only-export-components` rule on idiomatic co-located exports (user chose suppress over file-split).

User decided: **keep the lint cleanup bundled in PR 1 and just call it out in the PR description** (do NOT split into a separate PR). Reviewer should focus on `1fee161`, not the inert feature code.

## How to resume (BLOCKED — do this first)

Git auth is broken. Have the user restore it, e.g.:
```
! gh auth login        # GitHub.com → HTTPS → browser; yes to "authenticate Git"
```
(or `! gh auth refresh`, or fix SSH via `! ssh-add ~/.ssh/id_ed25519`).

Then, once push access is back:
1. `git push -u origin editor-polish-pr1-bridge`
2. Open the PR against `master`. Title e.g. `feat(openorg): guided-editor bridge + section specs (PR 1)`. **Body must call out** that it also carries a behavior-preserving lint cleanup of shared llmstxt-social files (see commit `1fee161` above), verified by `tsc` + 53 tests + build.
3. Merge into `master`.
4. Branch `editor-polish-pr2-fields` off the updated `master` and start **PR 2 — Field components (T2.1–T2.5)** per the plan.

## Verification commands (web)

```bash
cd packages/web
npx tsc --noEmit          # clean
npx vitest run            # 53/53
npm run lint              # exit 0 (was 17 errors + 10 warnings before 1fee161)
npm run build             # exit 0 ("build was canceled / Vite server closed" tail line is a cosmetic prerender-server shutdown artifact — exit code is 0)
```

## How to test the Open Org generator locally (existing feature, unaffected)

Domain: **`openorg.good-ship.co.uk`** (prod, may not be live yet — prod rebuild is still an open action item below). Local: `localhost:5173/openorg/generate`. Single Vite build + single FastAPI process serve both this and `llmstxt.social`, route tree chosen by `window.location.hostname`. Full click-through in `LOCAL.md` (needs `.env` with `ANTHROPIC_API_KEY` + `CHARITY_COMMISSION_API_KEY`; magic-link/claim emails print to API/worker stdout in dev).

---

> NOTE: everything below is the PRIOR Phase-1 handoff (2026-05-12). Kept for historical context — its action items (prod rebuild, DNS, env vars, key rotation, Murmurations upstream PR) are still open.

---

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
