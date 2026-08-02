# Handoff — Open Org hardening, essay-vision features, and Phase 2 federation/evidence build

> Session ended: 2026-07-05 (session 6)
> Branch: `master` — **14 files uncommitted in the working tree** (see Session 6). This checkout is bind-mounted into the live production containers (see the critical environment note below) — uncommitted edits here are already "live" the moment `api`/`celery_worker` restart, regardless of git state.
> Resumes at: **read the Session 6 environment-topology note before touching any container on this host.** Then: decide on production cleanup (stray `GB-CHC-1001635` row, duplicate `worker`/`beat` containers), review/commit the Session 6 diff, and only then return to the Session 5 deploy backlog (prod image rebuild + Tunnel route + Resend verify + Murmurations upstream PR + MCP/Hypercerts deploy wiring).

## TL;DR

Session 1 hardened Open Org (8 bugs, brand alignment, graph discovery, Claude skills). Session 2 tackled the essay's vision gaps: **funder signalling**, **evidence layer**, **profile evolution**, **cluster insights**, and **ideas-first discovery**. Session 3 made magic-link auth **request-aware** and committed ideas-first discovery. Session 4 added **rendered idea & strategy detail pages**, a fully interactive **graph** (drag, zoom controls, click-to-focus, polish), **titles** in lists/cards, and **rich demo seed data**; PR #22 (all of sessions 1–4) merged to master 2026-06-30. Session 5 built the full **Phase 2 spec** — evidence enrichers (Companies House, 360Giving v1), three CRM integrations (Beacon, Lamplight, Salesforce), an **MCP server**, per-record Murmurations federation, an **AT Protocol Lexicon design**, and a **Hypercerts** impact-claim pipeline — 12 steps, all TDD, merged directly to master. Session 6 set out to click-test the Phase 2 work locally and **discovered the "local" `llmstxt-local` docker-compose project on this Mac Mini is actually the live production stack** — not a sandbox. Several real bugs were found and fixed (dev-mode CORS/origin gaps, a misleading 409 error message, a hard theme-extraction failure that blocked *any* infrastructure-type charity from generating, a stale "we're emailing you" UI message on failure), all verified against the correct isolated `llmstxt-test` stack (port 8010) — but not before some real, low-impact production side effects occurred. **Read the Session 6 section in full before doing anything else on this host.**

## Session 6 (2026-07-05) — READ FIRST: environment topology

**This host runs both production and an isolated test stack, as two separate `docker compose` projects from the same checkout:**

| | `llmstxt-local` (production) | `llmstxt-test` (sandbox) |
|---|---|---|
| Compose files | `docker-compose.yml` + `docker-compose.single.yml` + `docker-compose.override.yml` | `docker-compose.test.yml` |
| API port | 8000 — `cloudflared` (`/etc/cloudflared/config.yml`) routes `llmstxt.social`/`www.llmstxt.social` **directly** to `http://127.0.0.1:8000`, no Caddy hop | 8010 |
| Postgres / Redis | 5432 / 6379 (internal only — see `docker-compose.override.yml`'s port reset) | 5442 / 6389 |
| Correct services | Exactly 5: `postgres redis api worker beat` (see `MISTAKES.md` 2026-06-11 entry) | `postgres redis api celery_worker` |
| Env | `.env` has `ENVIRONMENT=production`, but `docker-compose.yml`'s `api`/`celery_worker`/`celery_beat` services hardcode `ENVIRONMENT: development` — **the live site has been running in dev mode** (pre-existing, not caused this session) | `ENVIRONMENT: development` genuinely, by design |

**The naming is actively misleading** — "llmstxt-local" sounds like a local dev project but is the real internet-facing deployment. Before assuming any container on this host is a safe sandbox: check `docker inspect <container> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'`, check `/etc/cloudflared/config.yml`, and check `MISTAKES.md` for the documented 5-service production list.

**What this session did to production before catching the mistake** (all against `llmstxt-local`):
- Restarted `api`, `celery_worker`, `celery_beat` several times (brief real outages each time — `api` is the live internet-facing process).
- Added then removed a test evidence item on org `GB-CHC-9000006` (cleaned up, net no-op).
- Deleted a live magic-link rate-limit key from the shared production Redis (minor — narrow IP + hour-bucket scope).
- Ran the real generate pipeline twice for charity `GB-CHC-1001635` (NAVCA) — real Anthropic + Companies House + website-crawl calls, real spend. **That row is still sitting in the production DB with `generation_status: failed`** (pre-fix behaviour) — needs a decision: delete it, or let a future real generate retry pick it up now the fix is live.
- Logged in as `tomcampbellwatson@gmail.com` via the real magic-link flow — real `users`/`magic_link_tokens` rows now exist in production. No real email was sent (`RESEND_API_KEY` in `.env` is empty — Resend calls fail silently and are caught).

**`MISTAKES.md` directly contradicts itself on which pair is real — do not resolve this by guessing.** The 2026-06-11 entry says the production stack is exactly `postgres redis api worker beat`, implying `celery_worker`/`celery_beat` are the dev-style duplicate. A *separate* 2026-07-05 entry (written by something/someone else — not this conversation) says the opposite: that `worker`/`beat` are the orphaned pair "from before the services were renamed to `celery_worker`/`celery_beat`," and `celery_worker`/`celery_beat` are "the correctly-named, up-to-date" ones. Both entries agree on the *symptom* (duplicate containers racing on the same Redis queue, non-deterministically running stale vs. current code for every Celery-dispatched task since 2026-06-11 — generate, Murmurations submit/sync, subscription monitoring beat) but disagree on which container is the impostor. **Needs the user to determine ground truth (check each image's build date/git SHA against what's actually deployed) before anything gets stopped or removed** — guessing wrong means killing the real production workers.

**The actual test sandbox** — `llmstxt-test` (`docker-compose.test.yml`, header comment literally says "never touches the running `llmstxt-local` (production) stack") — had its `api`/`celery_worker` containers `Exited (137)` for 10 days. Brought back up + rebuilt this session:
```
docker compose -p llmstxt-test -f docker-compose.test.yml up -d --build api celery_worker
```
Ran `alembic upgrade head` there too (was one migration behind). All further local click-through testing should go through **`http://localhost:8010`**.

### Bugs found and fixed (all verified against `llmstxt-test`, not production)

1. **Dev-mode magic-link origin allowlist didn't recognise `openorg.localhost:5173`** — only `:3000` was listed, and port 3000 is taken by an unrelated project on this host. `routes/auth.py:_allowed_origins()`.
2. **Same gap in the CORS origins list** — `config.py:cors_origins_list` now carries the same dev-only extension (mirrors #1).
3. **The 409 "profile already exists" error surfaced as a generic "generate failed"** instead of the actual structured backend message, because the frontend's error-detail unwrapping only handled `string`/`Array` shapes, not the object `{"error": ..., "org_id": ..., "generation_status": ...}` the backend actually sends. `api/openorg.ts:generateProfile`.
4. **Any charity whose activities don't match the fixed 30-theme vocabulary failed generation outright** (`org_profile.schema.json` required `mission.themes` minItems 1). Real-world case: NAVCA (charity `1001635`, a sector-infrastructure body) — the LLM correctly found zero themes above the 0.7 confidence threshold, and the schema rejected the resulting empty array, aborting generation entirely rather than degrading gracefully as the existing error message already claimed ("owner can add themes manually after claiming"). Fixed: `minItems: 0` in the schema, removed the now-dead special-case raise in `generator.py`, updated `test_schemas.py`/`test_generator.py` (TDD red→green). Verified live against `llmstxt-test`: NAVCA now generates successfully with `mission.themes: []`.
5. **The "we're emailing you a one-time link" text stayed visible even after generation failed** — no claim email is ever sent on failure (`send_claim_email` only runs after `generation_status = "ready"`), so the promise was actively false once the live-status panel showed "Couldn't finish." `Generate.tsx` now hides that line once `statusQuery.data?.status === 'failed'`.

Verification: core 485 (unchanged count, one test repurposed) · API 275 (unchanged) · web 217 (+1) · `tsc` clean.

### Outstanding from Session 6

- **Decide on the `GB-CHC-1001635` row in production** — currently `failed` from before the fix; either delete or let it get retried for real.
- **Resolve the duplicate `worker`/`beat` vs `celery_worker`/`celery_beat` situation on `llmstxt-local`** — a deliberate stop/rm decision, not something to restart-away.
- **Review and commit the Session 6 diff** (14 files — see `git status`) — currently sitting uncommitted in a checkout that's bind-mounted into live production.
- Confirm whether the bundled SPA served by `llmstxt-test`'s `api` container (static build, not the Vite dev server) reflects the `Generate.tsx` fix, or needs a rebuild.

## Session 5 (2026-07-03)

Built the full Phase 2 spec (`open-org/open-org-phase2-spec.md` — drafted this session, currently **untracked/uncommitted**, worth committing for the record) on a new branch `feat/phase2-federation-evidence`, off master (which at that point already had PR #22 merged). All 12 steps landed as separate TDD commits, then the branch was merged into master with a merge commit (`715b9c7`) and **pushed straight to `origin/master`** — unlike every prior Open Org milestone (PRs #14–#22), no PR was opened for review. Worth a call on whether that's intentional going forward or whether this branch should get a retroactive look.

**The 12 steps** (commits `e3a1f59`..`b616ef6`):
1. **Companies House enricher** (`e3a1f59`) — governance data (officers, filing history, PSC, registered office, accounts) via HTTP Basic auth keyed on the `company_number` the CC enricher already extracts. Filing history maps to `evidence[]`.
2. **360Giving API v1 enricher** (`5202153`) — rewritten to query the 2024 REST API by `org_id` (`GB-CHC-{number}`) directly instead of bulk-file downloads. Grants map to `evidence[]`.
3. **MCP server** (`042724e`) — new `packages/mcp/` package (`openorg-mcp`), 7 public read-only tools (`get_profile`, `search_profiles`, `get_ideas`, `get_strategies`, `get_evidence`, `get_graph`, `get_themes`) + 4 resources, stdio + HTTP/SSE transport.
4. **Per-record Murmurations envelopes** (`9d98dae`) — `build_strategy_envelope()`/`build_idea_envelope()` plus two new draft Library schemas at `deploy/murmurations/` (`open_org_strategy-v0.1.0.json`, `open_org_idea-v0.1.0.json`).
5–7. **CRM read integrations** (`33e0c42`, `356d18b`, `7d97eea`) — Beacon, Lamplight, Salesforce enrichers (Pattern A — read only), each mapping donations/outcome measurements/grants to `evidence[]`.
8. **MCP admin tools** (`fbe194a`) — `sync_from_crm` (reads Beacon/Lamplight/Salesforce, returns evidence for human review — no auto-write) and `add_evidence` (validated, deduped append to a profile's `evidence[]`).
9. **Hypercerts module** (`4ccb004`) — `build_claim()` / `mint_claim()` / `fetch_hypercerts_for_org()` / `hypercert_to_evidence()`. Only evidence items with `evidence_type: "outcome_data"` and populated `outcomes[]` can be minted.
10. **MCP `mint_hypercert` tool** (`ebf8526`) — wraps the Hypercerts module: validates evidence, builds and submits the claim, writes the token reference back onto the evidence item.
11. **AT Protocol Lexicon design** (`5d98e20`) — spec-only doc at `deploy/atprotocol/openorg-lexicons.md`: six Lexicons mapped to the existing JSON schemas, a DID identity model (`did:web` vs `did:plc`), and a hybrid Murmurations/ATProto architecture. Implementation is deliberately gated on a Phase 4 decision — nothing to deploy here.
12. **CRM Pattern B — one-way push** (`7f421f1`, `b616ef6`) — `crm_push.py` maps Open Org profiles to each CRM's schema; POST write methods (`create_constituent`, `create_campaign`, etc.) added to all three CRM clients. Writes raise on HTTP error (reads degrade to `None`).

**Verified this session** — re-ran the full suites rather than trust commit-message counts, since the tracking docs were already stale once this session:
- `packages/core/tests/` — **485 passed**
- `packages/mcp/tests/` — **47 passed**
- `packages/api/tests/` — **275 passed** (unchanged — Phase 2 added no new API routes)
- `packages/web` vitest — **216 passed** (unchanged — Phase 2 was backend/MCP only, no frontend work)
- `tsc --noEmit` — clean

**Gaps between the Phase 2 spec and what actually landed:**
- **No REST API routes for Hypercerts.** Spec §5.2 calls for `POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert` and `GET /open-org/{org_id}/hypercerts[/{token_id}]`. Only the core module (`hypercerts.py`) and the MCP tool exist — minting/listing is only reachable via an MCP client, not the public API or web app.
- **MCP server isn't wired into the deploy stack.** `packages/mcp/` is a standalone package with its own `pyproject.toml`, but there's no `mcp` service in `docker-compose.yml` and it isn't behind Caddy/Tunnel. It only runs if launched manually.
- **No new env vars documented.** CLAUDE.md requires every secret to be an env var documented in `.env.example`. None of the following are in any `.env.example` yet: Companies House API key, Beacon/Lamplight/Salesforce credentials, or a Hypercerts custodial wallet key. Check each enricher/module's constructor for what it actually expects before deploying.
- **Murmurations upstream PR scope grew.** The long-standing outstanding action now covers three schema files, not one: `open_org_profile-v0.1.0.json` (Phase 1) plus `open_org_strategy-v0.1.0.json` + `open_org_idea-v0.1.0.json` (this session).

**Not gaps — deliberately deferred per the spec:** Donorfy/CiviCRM/Raisely CRM integrations, AT Protocol PDS/relay/App View deployment, org-owned Ethereum wallets, CRM webhooks/real-time sync, access control (moved to a separate "Phase 2.5" spec).

### Local dev testing pass (2026-07-03, same session)

Restarted `api`/`celery_worker`/`celery_beat` to load the merged code (no image rebuild needed — Phase 2 added no new pip deps), confirmed Alembic at head (`e4f5a6b7c8d9`), confirmed demo seed data present (15 orgs/17 ideas/7 strategies). Then exercised the actually-new pieces by hand rather than trusting the passing test suites, since they'd already been misleading once this session (see #28 below). Findings:

- **MCP public tools — genuinely work.** Ran `get_themes`, `search_profiles`, `get_profile`, `get_evidence`, `get_graph` against real seeded data (inside the `api` container's network, with `packages/mcp` + the `mcp` SDK installed ad hoc — it isn't part of the `api` image). All returned correct, sensible data (e.g. `search_profiles(theme="mental_health")` correctly matched 2 seeded orgs via the JSONB containment query).
- **MCP `add_evidence` — works, but has a real data-integrity bug.** Appending an evidence item updates `profile_json` only; `markdown_source` is left untouched. Since the markdown editor's `PUT` route treats `markdown_source` as canonical and regenerates `profile_json` from it on every save (locked decision #5, `PLAN.md`), the next time an admin saves that profile via the editor, the MCP-added evidence silently disappears. Reproduced live, then cleaned up the test evidence item afterward.
- **Per-record Murmurations envelopes are unreachable.** `build_strategy_envelope()`/`build_idea_envelope()` are real, tested, correct-looking functions — but nothing calls them. `GET /open-org/{org_id}/strategies/{slug}/murmurations.json` just falls through to the SPA (404 → HTML, not JSON). This was marked "✅ Done" in the previous doc pass based on the commit message and test count; correcting that here — it's built but dead code.
- **360Giving API v1 enricher is broken against the real API — the most severe finding.** Live-tested against Trussell Trust (`GB-CHC-1110522`, a real charity with 76+ grants on 360Giving):
  - `fetch_grant_summary()` raises an **uncaught `AttributeError`** (only catches `httpx.HTTPError, KeyError, ValueError`). The real endpoint returns `{"funder": {"aggregate": {"currencies": {"GBP": {...}}}}, "recipient": {...}}`; the parser expects `{"grants_received": {"amounts": {...}}, "is_funder": bool, ...}` — a completely different shape.
  - `fetch_grants_received()`/`fetch_grants_made()` don't crash but silently return **all-empty** `GrantRecord`s (title `""`, amount `0`, funder `""`, ...). The real endpoint nests each grant's actual fields under `result["data"]`; `_parse_grant()` reads fields off `result` directly.
  - All 19 unit tests for this module pass, because they mock the wrong response shape. This is a real API — no auth needed — so it's fully testable, and it needs a rewrite against the actual v1 responses (captured live above) before it's usable.
- **Hypercerts `build_claim()` works as a pure function** — no wallet needed to verify the claim-construction logic; tested with a synthetic outcome-data evidence item and got a sane `HypercertClaim` back.
- **Not tested (need credentials I don't have):** Companies House enricher, Beacon/Lamplight/Salesforce CRM enrichers (read or write). Given the 360Giving finding, don't assume these are correct just because their unit tests pass — the same failure mode (mocks describing an imagined API shape rather than the real one) could apply. Worth a live sandbox check before relying on any of them.
- **Environment note, not a bug:** `localhost:5432` on this machine is bound to an unrelated project's Postgres container (`open-question-bank-db-1`), not this project's. `llmstxt-local-postgres-1` doesn't currently publish a host port at all despite `docker-compose.yml` saying `5432:5432` (likely lost the binding to the port conflict at some point). Testing anything DB-backed from the host directly will silently hit the wrong database — run it inside the compose network instead (`docker compose run` / `exec`).

## Session 4 (2026-06-30)

All committed and pushed to PR #22 (`79d59a8` is the tip).

- **Dev `/open-org` proxy fix** (`e8723e0`) — the public API routes live at `/open-org/*` (federation-friendly), but Vite only proxied `/api/*`, so profile/idea/strategy/history fetches fell through to the SPA fallback and the detail pages errored in dev. Added `/open-org` to the Vite proxy (prod is unaffected — FastAPI serves both from one origin).
- **Rendered idea & strategy detail pages** (`635ae40`, `3f26e41`) — new routes `/openorg/:orgId/ideas/:slug` and `/openorg/:orgId/strategies/:slug`, styled like the org profile. Extracted shared presentation into `components/openorg/detail.tsx` + `detailFormat.ts` (ProfileDetail reuses them). Idea/strategy cards + profile lists + graph node panels now link to these pages; the raw `.json` survives as a "view raw JSON" link.
- **Graph interaction + polish** (`39246c1`, `66beb44`) — drag nodes to reposition (pin/double-click-release), on-screen zoom **+/−/Fit/Reset** controls, click-to-focus neighbours, smoother physics (velocity/alpha damping), soft node shadows, teal focus rings, background vignette, pinned-node indicator.
- **Graph zoom-binding fix** (`79d59a8`) — zoom/pan was bound in a `useEffect([])` that ran before the conditional `<svg>` existed, so it never attached on a cold load (only survived via HMR). Moved binding to a **callback ref** so it attaches when the svg mounts.
- **Titles in lists/cards** (`821fc9c`) — `title` now flows through the discovery idea rows and public list summaries (API `_record_summary` + `IdeaRow`); cards/lists show the real title, falling back to slug. +1 API test.
- **Rich demo seed data** (`66beb44`) — `packages/api/scripts/seed_openorg_demo.py` enriches all 17 ideas + 7 strategies with schema-valid content (idempotent; validates + regenerates markdown). `StrategyDetail` renders the structured relationships/funding-mix/learning shapes; `IdeaDetail` shows the evidence base. See the **Demo seed data** section below for how to run it.

## Session 3 (2026-06-26)

- **Ideas-first discovery committed** (`4f9a54f`) — leaflet mock fixed; `Discover.test.tsx` green; the session-2 blocker is gone.
- **Request-aware magic links** (`6eeb72e`) — `/auth/magic-link` builds the link from the request `Origin`, validated against `MAGIC_LINK_ORIGIN_ALLOWLIST` (exact match), falling back to `FRONTEND_URL`. One shared FastAPI process now sends correct login links for both products without repointing `FRONTEND_URL`.
- **Open Org email branding by host** (`11b27f8`) — magic-link emails use Open Org branding + `hello@openorg.good-ship.co.uk` sender when the request comes from the openorg host.
- **Tests + docs** (`e7ff6e4`, `6125e71`) — origin-allowlist bypass pinned, endpoint branding wiring tested (+10 API tests → 274), `.env.example` + CLAUDE.md updated.
- **Lint fix** — `themeChips` inlined into its `useMemo` to clear the only outstanding exhaustive-deps warning.

## What landed this session (8 new commits, 20→22 total on branch)

### 1. Semantic edge visualisation (commit 5)
Six edge types in the graph API: `strategy_idea`, `idea_idea_shared_theme`, `idea_idea_shared_place`, `idea_org_connection`, `strategy_strategy_shared_theme`, `idea_idea_explicit`. Distinct visual styling per type, arrowheads, hover labels, "show only explicit" toggle.

### 2. Cluster insights (commit 6)
Graph summary now surfaces meaningful cluster descriptions — org names, ideas summary, places, dominant themes, human-readable sentences like *"2 organisations (Riverside Trust, Beta Trust) and 1 idea around food_access, health in Great Yarmouth"*. Clickable cluster cards dim non-cluster nodes. Cluster colour-coding toggle. API 234 (+6), Web 187 (+5).

### 3. Profile evolution (commit 7)
Three new features:
- **Version history API** — `GET /open-org/{org_id}/history` returns chronological timeline across profile + strategies + ideas. Per-record history endpoints too.
- **Timeline on profile detail** — vertical timeline showing the org's trajectory.
- **Status badges** — ideas and strategies show coloured status badges + created/updated timestamps.
- API 245 (+11), Web 191 (+4).

### 4. Funder signalling + evidence layer (commit 8 — combined)

**Funder signalling:**
- `OrgSignal` model + Alembic migration (`org_signals` table)
- `POST /api/open-org/ideas/{org_id}/{slug}/signal` — public, all fields optional
- `GET /api/open-org/ideas/{org_id}/{slug}/signals` — list signals on one idea
- `GET /api/open-org/{org_id}/signals` — aggregated signals for an org
- `SignalButton` component with form (name, email, message — all optional)
- `FunderInterestSection` on profile detail with expandable per-idea rows
- Interest count badge on Ideas page cards
- 11 API tests + 4 web tests

**Evidence layer:**
- Top-level `evidence` array in `org_profile.schema.json` (evidence_id, title, description, evidence_type, date, url, themes, outcomes)
- Converter: `parse_evidence()` / `render_evidence()` for `## Evidence` section with `### {evidence_id}: {title}` subsections
- Evidence section on ProfileDetail with coloured type badges, themes, outcomes, URL links
- Evidence template with guided comments in `openorgTemplates.ts`
- 11 converter tests + 5 ProfileDetail evidence tests
- Existing `mission.evidence_summary` stub kept for backward compat

### 5. Ideas-first discovery (commits pending — API done, frontend in progress)

**API (committed in working tree, not yet committed to git):**
- `GET /api/open-org/discover/ideas/summary` — returns `{total_ideas, total_orgs, themes_breakdown, status_breakdown}`
- `sort` query param on `GET /api/open-org/discover/ideas`: `signals` (most interest first), `recent`, `status` (maturity order)
- 8 new API tests (264 total API tests pass)

**Frontend (written, not yet committed — test has a bug):**
- `Discover.tsx` rewritten: Ideas view is the default (not Organisations)
- Hero summary: "N ideas from M organisations across K themes"
- Theme chips with counts from summary (multi-select, client-side refinement)
- Place filter, status filter, sort dropdown
- Idea cards with signal count, status badge, cost range, org name
- `Discover.test.tsx` created (7 tests) but **hangs vitest** — root cause: `vi.mock('leaflet')` factory was missing `default` export key, causing `L.Icon.Default.mergeOptions` to crash at module load. Fix identified (add `default: { Icon: { Default: { mergeOptions: () => {} } } }` to mock) but not yet verified.

## All commits on branch (22 total)

```
07477c0 feat(openorg): add funder signalling and evidence layer
96f55e4 feat(openorg): add evidence layer to profile schema and converter
4038c17 feat(openorg): show profile evolution — version history timeline and status badges
4b43f03 feat(openorg): surface meaningful cluster insights in graph discovery
94b8751 feat(openorg): add semantic edge visualisation to graph discovery
5578502 feat(openorg): add semantic connections to graph API
15b801f docs: update HANDOFF for Good Ship brand alignment
fbf9bab style(openorg): align with actual Good Ship brand tokens
56b88a3 docs: update STATE.md and HANDOFF.md for hardening session
1aa6070 feat(openorg): add Claude skills for /org-strategy and /org-idea
c4249a0 feat(openorg): add force-directed graph discovery view
29f9968 feat(openorg): add graph data API endpoint for discovery visualisation
d4c68a4 style(openorg): align design system with editorial palette + sage accents
2df0e23 fix(openorg): coerce unquoted numeric YAML scalars to strings per schema
0cc7a47 test(openorg-creator): verify create/get route method disjointness
677abff fix(openorg): parse plain (non-bold) items in not_doing/tensions sections
6615c47 fix(openorg-creator): extract DOCX tables, headers, and footers
08cb770 fix(openorg): parse and render strategy priorities from body sections
769be06 fix(openorg-creator): emit SSE error event when LLM stream throws mid-turn
f0be6fa fix(openorg): mask fenced code blocks before splitting body sections
a5656ac fix(api): ignore extra env vars in Settings model
```

## Uncommitted working tree state

Branch is clean of feature work — everything above is committed and pushed.

```
M packages/web/public/sitemap.xml   (unrelated llmstxt.social route/date churn from another session — left out of this PR)
```

## How to resume

The branch is feature-complete and green. The remaining work is **deployment** (all user actions — see below) plus two follow-ups (Murmurations upstream PR, editor-polish PR 7).

### Re-run the full verification gate

```bash
# Python (from repo root)
.venv/bin/python -m pytest packages/core/tests/ -q    # 325 passed
.venv/bin/python -m pytest packages/api/tests/ -q     # 274 passed

# Web (from packages/web)
npx tsc --noEmit                                        # clean
npx vitest run                                          # 208 passed
npm run lint                                            # clean
```

## Demo seed data

The demo dataset (14 orgs, 17 ideas, 7 strategies) ships with titles + themes
only. Rich, schema-valid content for the idea/strategy detail pages is applied
by an idempotent enrichment script:

```bash
docker exec llmstxt-local-api-1 python /app/api/scripts/seed_openorg_demo.py
```

It validates each record against the Open Org schemas, regenerates the markdown
source, and commits. Re-running is safe. Content lives in
`packages/api/scripts/seed_openorg_demo.py` (`IDEA_ENRICHMENTS` /
`STRATEGY_ENRICHMENTS`, keyed by `(org_id, slug)`).

## Deploy notes

- **Rebuild the prod image before deploy** — `config.py` imports `openai` at boot (provider abstraction), web package has `d3` + `@fontsource-variable/dm-sans` dependencies. A stale image will crash.
- New env vars in `.env.example` already documented (`LLM_PROVIDER`, `LLM_MODEL`, `OPENROUTER_*`, `OLLAMA_*`).
- `packages/core` edits need a test-stack container restart (uvicorn `--reload` doesn't watch `/app/core`).
- D3 adds ~50KB to the web bundle, but GraphDiscovery is lazy-loaded.

## Flagged, not fixed

- Cross-product SSO cookie can't span `llmstxt.social` + `good-ship.co.uk` (product decision — documented in CLAUDE.md).
- Rate-limit real-client-IP behind Cloudflare/Caddy — verify `trusted_proxies` from a real external client.
- Cosmetic: idea/strategy cards show raw slugs as titles; `/discover/ideas` `area_code` filter is a no-op.
- Editor polish PR 7 (keyboard + motion polish) — still outstanding.
- Murmurations schema not yet registered upstream (now 3 schemas — see Outstanding user actions).
- Hypercerts REST API routes not built — core module + MCP tool only (session 5 gap).
- MCP server (`packages/mcp/`) not wired into `docker-compose.yml` or Caddy — package exists, nothing runs it (session 5 gap).
- New Phase 2 integrations (Companies House, Beacon, Lamplight, Salesforce, Hypercerts wallet) have no documented env vars yet (session 5 gap).

## Outstanding user actions

1. ~~**Open PR #22**~~ — ✅ merged 2026-06-30 (session 4)
2. **Murmurations schema upstream PR** — now 3 schemas at `deploy/murmurations/` (profile + strategy + idea)
3. **Cloudflare Tunnel route** for `openorg.good-ship.co.uk`
4. **Resend domain verification** for `hello@openorg.good-ship.co.uk`
5. **Prod image rebuild + deploy** — stale image lacks `openai` + D3 + `@fontsource-variable/dm-sans` deps and will crash on boot
6. **Editor polish PR 7** (keyboard + motion polish)
7. **Decide on Phase 2 branch review** — `feat/phase2-federation-evidence` merged straight to `origin/master` with no PR; decide whether to review it retroactively
8. **Commit or discard `open-org/open-org-phase2-spec.md`** — currently untracked; it's the spec that drove session 5's build
9. **Provision + document Phase 2 credentials** — Companies House API key, Beacon/Lamplight/Salesforce API credentials, Hypercerts custodial wallet key — none exist in any `.env.example` yet
10. **Decide MCP server deployment** — add an `mcp` service to `docker-compose.yml` + Caddy route, or leave it as a local-only/manually-run package for now
11. **Fix the 360Giving v1 enricher** — broken against the real API (see local dev testing pass above); currently unusable for any real charity
12. **Fix `add_evidence` MCP tool** — needs to regenerate/update `markdown_source` alongside `profile_json`, or evidence added via MCP will vanish on the next editor save
13. **Wire per-record Murmurations envelopes to an actual route** — `build_strategy_envelope`/`build_idea_envelope` are dead code without one
14. **Live-verify the CRM enrichers** (Companies House, Beacon, Lamplight, Salesforce) against real sandbox data before trusting them — the 360Giving bug shows unit tests alone (all mocked) aren't sufficient evidence here

## Remaining essay-vision gaps

- **#4 Access control / audit trail** — moved to a separate "Phase 2.5" spec. OrgVersion audit trail exists; proper tiered access control is not built.
- **#5 Local agent / evidence integration** — ✅ Done (session 5). CRM enrichers (Beacon/Lamplight/Salesforce) + MCP `sync_from_crm`/`add_evidence` tools feed `evidence[]` from external systems; the agent is conversation-driven via MCP (human reviews before write), matching the essay's framing rather than a background daemon.
- **#7 Funder-facing view** — Ideas-first discovery partly addresses this. A dedicated funder-perspective lens could be built on top of the graph + signals data.