# Handoff — Open Org hardening + essay-vision features

> Session ended: 2026-06-26 (session 3)
> Branch: `fix/openorg-hardening` (off `master`) — **pushed, PR open, all gates green**
> Resumes at: **deploy** (prod image rebuild + Tunnel route + Resend verify), then Murmurations upstream PR and editor-polish PR 7

## TL;DR

Session 1 hardened Open Org (8 bugs, brand alignment, graph discovery, Claude skills). Session 2 tackled the essay's vision gaps: **funder signalling**, **evidence layer**, **profile evolution**, **cluster insights**, and **ideas-first discovery**. Session 3 closed out the loose ends: the `Discover.test.tsx` leaflet mock is fixed, ideas-first discovery is committed, and magic-link auth is now **request-aware** (base URL derived from a validated `Origin`, Open Org email branding by host). The branch is **green on every gate** (core 325 · API 274 · web 208 · tsc · lint) and the **PR is open**. The only thing left before openorg.good-ship.co.uk goes live is deployment — all user actions.

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
- Murmurations schema not yet registered upstream.
- Rate-limit real-client-IP behind Cloudflare/Caddy — verify `trusted_proxies` from a real external client.
- Cosmetic: idea/strategy cards show raw slugs as titles; `/discover/ideas` `area_code` filter is a no-op.

## Outstanding user actions

1. ~~**Open PR**~~ — ✅ opened 2026-06-26 (session 3)
2. **Murmurations schema upstream PR** — schema at `deploy/murmurations/`
3. **Cloudflare Tunnel route** for `openorg.good-ship.co.uk`
4. **Resend domain verification** for `hello@openorg.good-ship.co.uk`
5. **Prod image rebuild + deploy** — stale image lacks `openai` + D3 + `@fontsource-variable/dm-sans` deps and will crash on boot
6. **Editor polish PR 7** (keyboard + motion polish)

## Remaining essay-vision gaps (not started)

- **#4 Access control / audit trail** — Phase 2 per spec. OrgVersion audit trail exists; proper tiered access control is Phase 2.
- **#5 Local agent / evidence integration** — Phase 2 per spec.
- **#7 Funder-facing view** — Ideas-first discovery partly addresses this. A dedicated funder-perspective lens could be built on top of the graph + signals data.