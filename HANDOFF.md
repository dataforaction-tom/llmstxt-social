# Handoff — Phase 1.5 baselined + editorial design pass

> Session ended: 2026-05-11
> Branch: `master` (post-merge of this PR)
> Picks up from: end of frontend polish, dev-mode magic-link logger, and the civic-editorial design pass
> Resumes at: local click-through against `LOCAL.md`, then operator follow-ups

## TL;DR

Three PRs landed this session (in order):

- **PR #6** (squash `99bfee2`) — Phase 1 + 1.5 + frontend polish: the Open Org sub-application, schema v0.2 prompt/crawler iteration, all baseline reports v0.1 → v0.4, CodeMirror editor, chat creator, strategy/idea editor pages, Vitest+RTL setup.
- **PR #7** (squash `86c7fbe`) — `chore(dev): log magic + claim links to stdout in development mode` + `LOCAL.md` walkthrough.
- **PR #8 (this PR)** — civic-editorial design pass on the Open Org SPA + the four code-review fixes flagged in the same pass.

The v0.4 baseline scorecard (10 UK charities) is **6/6 must-pass green**. Local click-through is wired and ready to drive.

## Design pass — what landed

Aesthetic direction: civic editorial. The platform reads like a thoughtful public-sector publication rather than a SaaS app — a fit for the UK social-sector audience.

Foundation (added once, used everywhere):
- **Fonts (self-hosted via `@fontsource`)**: Fraunces (variable serif, opsz axis) for display; Public Sans (USDS — designed for accessible government documents) for body; JetBrains Mono for technical strings.
- **Palette extension** in `tailwind.config.js`: kept `primary-*` sky blue; added `paper #FAF7F2`, `paper-2 #F2EDE3`, `ink #1A1814`, `muted #6E6859`, `rule #D9D2C2`. Opt-in via `surface-paper` so other pages aren't touched.
- **Component classes** in `index.css` `@layer components`: `.kicker`, `.display-head`, `.surface-paper`, `.rule-h`, `.num`, `.editorial-preview` (single source of truth for rendered-markdown styling).

Per-page changes:
- **Discover** — editorial header (kicker + serif headline), filter band with underline-style inputs, active-filter chips, hairline-divider result list with serif name + italic area + `#tag` mono themes, staggered card reveal.
- **Create** — pre-session editorial brief + dashed-rule file upload; active session is a two-pane bordered surface with a role-rule transcript (left ink rule for user, primary rule for assistant — no chat bubbles) and a paper-tone live draft.
- **EditProfile / EditStrategy / EditIdea** — editorial header with kicker + serif title + mono `org_id`.
- **MarkdownEditor** — bordered container with hairline split between Source and Preview, kicker labels per pane, frontmatter collapsed behind `<details>`.

Code-review fixes that landed in the same PR:
- Self-hosted fonts replaced the original Google Fonts CDN (per CLAUDE.md: don't add deps without asking; local-first).
- `.editorial-preview` styles lifted from inline `<style>` blocks in `MarkdownEditor` + `Create` into a single `index.css` block (per CLAUDE.md: reuse before rewrite).
- `muted` darkened `#7A7468` → `#6E6859` so body copy meets WCAG AA (4.33:1 → 5.24:1). `text-muted/70` modifiers removed.
- OpenStreetMap `TileLayer` attribution restored as a clickable anchor per tile usage policy.

## State at handoff

| Step | Status | Notes |
|------|--------|-------|
| 0 — Schemas + themes + validator | ✅ Done |
| 1 — Markdown ↔ JSON converter | ✅ Done |
| 2 — DB models + Alembic migration | ✅ Done | Head `c2d3e4f5a6b7` |
| 3 — CachedAnthropic + llm_usage | ✅ Done | `tools`/`tool_choice` support |
| 4 — Editor + magic-link admin auth | ✅ **Done** | CodeMirror 6 + preview + strategy/idea editor pages + Vitest+RTL + the editorial design pass. |
| 5 — Profile generator | ✅ Done |
| 6 — Murmurations schema YAML | ✅ Drafted | **User opens upstream PR**. |
| 7 — Murmurations connector | ✅ Done |
| 8 — Strategy/idea chat creator | ✅ Done | SSE chat-creator page at `/openorg/:orgId/create/:kind`. |
| 9 — Discovery page | ✅ Done |
| 10 — Subdomain routing + Caddy | ✅ Done | `AUTH_COOKIE_DOMAIN` env-driven, Caddyfile updated, `HostRoot` redirect. |
| 11 — Real-world testing harness | ✅ Done + baselined v0.1 → v0.4 |
| **Phase 1.5 — schema v0.2 iteration** | ✅ Done | v0.2.1 → v0.2.7, all 6/6 must-pass at v0.4. |
| **Editorial design pass** | ✅ Done | Civic-editorial type system + paper palette + per-page polish + four code-review fixes. |

## v0.1 → v0.4 baseline scorecard

| Criterion | v0.1 | v0.2 | v0.3 | v0.4 |
|---|---|---|---|---|
| Trussell `food_access` | ❌ | ✅ | ✅ | ✅ |
| Shelter `housing_and_homelessness` | ❌ | ❌ | ❌ | ✅ |
| Mind `mental_health` | ❌ | ❌ | ✅ | ✅ |
| NSPCC `children_and_young_people` | ❌ | ✅ | ✅ | ✅ |
| Macmillan `families_and_carers` | ❌ | ✅ | ✅ | ✅ |
| ≥3 orgs no spurious `education` | n/a | 6/7 | 5/7 | 6/7 |

Reports committed at `tests/reports/baseline_v0.{1,2,3,4}.md`.

## Action items for the user

Pre-deploy:
1. **Walk through `LOCAL.md`** with `docker compose up` to feel the UX end-to-end. Dev-mode magic-link logger means no Resend setup needed.
2. **Open the Murmurations upstream PR** from `deploy/murmurations/`. Schema name: `open_org_profile-v0.1.0`. Connector defaults to test-index until the upstream merges.
3. **Verify Resend domain** for `hello@openorg.good-ship.co.uk` (needed for prod magic-link + claim email deliverability).

Deploy:
4. **Set production env vars**:
   - `AUTH_COOKIE_DOMAIN=.good-ship.co.uk`
   - `MURMURATIONS_INDEX_URL` + `MURMURATIONS_LIBRARY_URL` — flip from test-index once the schema PR merges.
5. **Add Cloudflare Tunnel route** for `openorg.good-ship.co.uk`:
   ```
   cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk
   ```
6. **Reload Caddy** with the new Caddyfile.

## How to run things

**Backend tests** (in `python:3.11-slim` container):
```bash
docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core[dev] -e "packages/api[dev]"
  cd packages/core && python -m pytest tests/ -q
  cd ../api && python -m pytest tests/ -q
'
```
Expected: 268 core + 122 api = **390 backend** green.

**Frontend**:
```bash
docker run --rm -v "$(pwd)/packages/web:/work" -w /work node:20-alpine sh -c '
  npm install --silent && npx tsc --noEmit && npm test
'
```
Expected: tsc clean, **5/5 vitest** green.

**Real-world harness**:
```bash
docker run --rm --env-file .env -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core -e packages/cli > /dev/null
  playwright install --with-deps chromium > /tmp/pw.log 2>&1
  llmstxt openorg test-corpus
'
```
Cost: ~$0.15 for 10 charities. Outputs to `tests/reports/real_world_run_<ts>.md` (git-ignored). Promote a vetted run to `tests/reports/baseline_v0.5.md` to update the reference.

**Local click-through**: see `LOCAL.md`. tl;dr:
```bash
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head    # one-time per fresh DB
docker compose up api celery_worker                  # magic links log here
# in another terminal:
cd packages/web && npm install && npm run dev        # http://localhost:5173
```

## Open follow-ups

None block ship; pick whatever helps next.

- **Chromium in the `celery_worker` Docker image** so the v0.2.6 Playwright fallback fires in compose runs. Currently the worker only runs httpx.
- **Step 4 last bits**: history restore endpoint + UI; publish/unpublish button in the SPA (backend exists).
- **Rate limiting on `/api/open-org/generate`** + route-layer £0.50/org/day cap.
- **Daily Celery beat** to evict expired `CreatorSession` rows.
- **Murmurations node deletion** when an OrgProfile is unpublished.
- **Live ONS centroid coverage** beyond UK nations + major cities; `refresh_from_ons` CLI hook.
- **`GET /api/open-org/areas`** typeahead for the discovery filter.
- **Postgres integration tests** for the JSONB filter paths.
- **API tenant gating per host** (deliberately deferred — revisit when real logs show traffic on the wrong host).
- **Diff-vs-baseline mode** for the harness.
- **Firecrawl as a third fetch tier** (only if a future corpus surfaces sites that defeat both httpx and Playwright).
- **Design-pass leftovers from review** (lower scores, didn't make the >=80 bar but worth tracking): result-card `<h2>` semantics, file-input focus indicator, form-input focus ring beyond the 1px border, link underlines at rest on the Discover org name.

## Notable decisions made this session

- **Phase 1.5 build order** (v0.2.1 → v0.2.7) was driven entirely by the `baseline_v0.1.md` report. Each step had a measurable target and a re-baseline. By v0.4 every must-pass criterion was green.
- **v0.2.1**: website-crawl augmentation is the highest-leverage theme-quality lever. Wired in via injectable `collect_website_text` in the generator.
- **URL normalisation** for bare `www.example.org` hostnames was a bug surfaced by running the harness. Now in `_normalise_url` inside `website_text.py`.
- **v0.2.6 Playwright fallback** with low-signal trigger (empty result OR single thin page) closed Mind. Wrapped the existing `crawler_playwright.PlaywrightCrawler`; no new infra dep.
- **v0.2.7 homepage-by-URL override** in `_extract_relevant_bodies` fixed Shelter without touching the shared `extractor.classify_page_type`.
- **Firecrawl held in reserve.** v0.4 baseline shows the local two-tier (httpx → Playwright) is enough for the 10 charities tested.
- **Frontend polish scope** chose Editor + chat UI + Vitest in one pass. The chat creator uses fetch + ReadableStream for SSE (EventSource doesn't allow POST bodies).
- **Dev-mode magic-link logger** skips Resend when `ENVIRONMENT=development` and prints the URL to stdout. Lets the local click-through work without verified-domain deliverability.
- **Editorial design direction** (Fraunces + Public Sans + paper/ink palette) chosen for civic-sector fit. Self-hosted via `@fontsource` after a review-flagged Google Fonts dependency.
- **`.editorial-preview`** lives once in `index.css` and is reused by both `MarkdownEditor` and `Create` — code-review fix per "reuse before rewrite".

## Files of note added/changed this session

- `LOCAL.md` — full local click-through walkthrough.
- `packages/core/src/llmstxt_core/playwright_fetch.py` — Playwright wrapper.
- `packages/core/src/llmstxt_core/open_org/website_text.py` — httpx → Playwright orchestrator with homepage-URL override.
- `packages/web/src/pages/openorg/{EditStrategy,EditIdea,Create,Discover}.tsx`, `EditProfile.tsx` — editor pages, chat creator, discovery — all redesigned in the editorial pass.
- `packages/web/src/components/openorg/MarkdownEditor.tsx` — CodeMirror + react-markdown editor with shared `.editorial-preview` styling.
- `packages/web/tailwind.config.js`, `packages/web/src/index.css`, `packages/web/index.html`, `packages/web/src/main.tsx` — design-system foundation (fonts, palette, utility classes).
- `packages/web/vitest.config.ts` + `src/test/setup.ts` + `MarkdownEditor.test.tsx` — Vitest+RTL bootstrap with 5 smoke tests.
- `tests/reports/baseline_v0.{1..4}.md` — every harness run, committed.
- `packages/api/tests/test_dev_magic_link_logger.py` — pins dev/prod email path behaviour.

## How to resume

After `cd /Users/tomcwxyz/llmstxt-local`:

```
Read CLAUDE.md, then PLAN.md, then HANDOFF.md. Phase 1 + 1.5 + design pass
are merged. Status check + propose next focus.
```

Likely next foci, depending on appetite:
- **Walk through `LOCAL.md` in person** to feel the UX after the design pass, then file roughness.
- **Worker Chromium** so the harness exercises the Playwright fallback in compose.
- **Phase 2 planning** (access control + grants, MCP integrations, funder profiles).
