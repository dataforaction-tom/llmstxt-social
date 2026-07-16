# State

> Last updated: 2026-07-05 (session 6)
> See `HANDOFF.md` for the full session wrap-up and resume instructions.

## Environment topology — read before running any docker command on this host

This Mac Mini runs **both** production and an isolated test stack, as two separate `docker compose` projects sharing one checkout (`/Users/tomcwxyz/llmstxt-local`):

- **`llmstxt-local` = production**, despite the name. `cloudflared` (`/etc/cloudflared/config.yml`, running as a live tunnel) routes `llmstxt.social` straight to `http://127.0.0.1:8000` — no Caddy hop. Both `worker`/`beat` AND `celery_worker`/`celery_beat` are currently running simultaneously, racing for the same Redis queue. **`MISTAKES.md` contradicts itself on which pair is the real one** (2026-06-11 entry says `worker`/`beat`; a separate 2026-07-05 entry says `celery_worker`/`celery_beat`) — unresolved, do not stop either pair without first establishing ground truth (compare image build dates/git SHAs against what's actually deployed).
- **`llmstxt-test` = the real sandbox** — `docker-compose.test.yml`, ports 8010 (api) / 5442 (postgres) / 6389 (redis), its own Postgres volume. Bring it up with `docker compose -p llmstxt-test -f docker-compose.test.yml up -d --build api celery_worker`. Use **this** for all local click-through / generation testing.

Before treating any container on this host as a disposable dev sandbox: `docker inspect <name> --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'` and cross-check `/etc/cloudflared/config.yml` + `MISTAKES.md`.

## System state diagram

```mermaid
stateDiagram-v2
    [*] --> Spec: spec written
    Spec --> Planning: read spec, lock decisions
    Planning --> Building: 12 decisions locked, plan persisted
    Building --> Testing: all 11 steps complete
    Testing --> Deploying: tests pass + security review
    Deploying --> Live: Caddy + Tunnel routes openorg.good-ship.co.uk
    Live --> Hardening: bug sweep + styling + graph discovery + Claude skills
    Hardening --> Vision: funder signalling, evidence layer, profile evolution, cluster insights, ideas-first discovery
    Vision --> Auth: request-aware magic links + Open Org email branding by host
    Auth --> Surfaces: rendered idea/strategy pages + interactive graph + rich seed data
    Surfaces --> Phase2: PR #22 merged; evidence enrichers, CRM integration, MCP server, federation, Hypercerts
    Phase2 --> LocalTest: click-through testing on llmstxt-test; 5 real bugs found + fixed
    LocalTest --> [*]: 14 files uncommitted on master; production cleanup + commit review pending

    note right of LocalTest: ← WE ARE HERE (fixes verified on llmstxt-test:8010; production has stray test data + duplicate worker/beat still unresolved; nothing committed yet)
```

## Component status

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 0 | Schemas + theme vocab + validator | ✅ Done | 30-theme vocab, three v0.1 schemas, jsonschema-Draft202012 validator wrapper. Evidence array added to profile schema. |
| 1 | Markdown ↔ JSON converter | ✅ Done + hardened | Round-trip identity; code-block masking, priority parsing, plain-bullet parsing, numeric type coercion, evidence section parsing added |
| 2 | DB models + Alembic migration | ✅ Done + extended | 9 models (added OrgSignal) with structural tests. New migration for org_signals table. |
| 3 | CachedAnthropic + llm_usage logging | ✅ Done | Provider-neutral (Anthropic/OpenRouter/Ollama) |
| 4 | Markdown editor UI + magic-link auth | ✅ Done | Dual-surface (guided + markdown), autosave, PublishStrip, live generate status |
| 5 | Profile generator | ✅ Done | CC + website crawl + analyzer + theme extractor + mission rewriter + ONS lookup |
| 6 | Murmurations schema upstream PR | ⚠️ User action needed | Schema + reference profile drafted at `deploy/murmurations/` |
| 7 | Murmurations connector + postcodes.io | ✅ Done + hardened | Health-check crash fixed, publish-before-validate guard added |
| 8 | Strategy/idea chat creator | ✅ Done + hardened | SSE error handling, DOCX table/header/footer extraction, priorities/learning data-loss fix |
| 9 | Discovery page | ✅ Done + enhanced | Ideas-first default view + hero summary + theme chips + List+Map view + Graph view (D3 force-directed) |
| 10 | Subdomain routing + Caddy | ✅ Done | Caddyfile dual site blocks; Layout.tsx hostname-aware (editorial chrome on openorg.*) |
| 11 | Real-world testing harness | ✅ Done + baselined | 10 UK charities baseline run |
| 12 | Claude skills (/org-strategy, /org-idea) | ✅ Done | SKILL.md files with full conversational flows, schema refs, theme vocab |
| 13 | Design system alignment | ✅ Done | Actual Good Ship brand tokens (navy/cream/teal/amber/DM Sans), 11 hover leaks fixed, editorial Layout chrome |
| 14 | Graph data API | ✅ Done | `GET /api/open-org/graph` — nodes + edges + 6 semantic edge types + cluster summary with enriched descriptions |
| 15 | Semantic edge visualisation | ✅ Done | Distinct styling per edge type, arrowheads, hover labels, "show only explicit" toggle, cluster colour-coding toggle |
| 16 | Cluster insights | ✅ Done | Org names, ideas summary, places, dominant themes, human-readable descriptions in graph summary; clickable cluster cards |
| 17 | Profile evolution | ✅ Done | Version history API (org/strategy/idea), timeline on profile detail, status badges, created/updated timestamps |
| 18 | Funder signalling | ✅ Done | OrgSignal model, 3 API endpoints, SignalButton component, FunderInterestSection, interest badge on Ideas page |
| 19 | Evidence layer | ✅ Done | Top-level `evidence` array in profile schema, converter parse/render, Evidence section on ProfileDetail, editor template with guided comments |
| 20 | Ideas-first discovery | ✅ Done | API (summary endpoint + sort param) + rewritten Discover.tsx (ideas-first default, hero summary, theme chips, place/status/sort filters). Leaflet mock fixed; Discover.test.tsx green. |
| 21 | Request-aware magic links | ✅ Done | `/auth/magic-link` derives the base URL from the request `Origin` validated against `MAGIC_LINK_ORIGIN_ALLOWLIST` (exact match), falling back to `FRONTEND_URL`. Open Org branding + `hello@openorg.good-ship.co.uk` sender selected by host. One shared FastAPI process now sends correct links for both products. |
| 22 | Idea & strategy detail pages | ✅ Done | Rendered routes `/openorg/:orgId/ideas/:slug` + `/strategies/:slug`, shared `components/openorg/detail.tsx`. Cards/lists/graph link here; raw JSON kept as a link. Titles surfaced through discovery + list summaries. |
| 23 | Interactive graph | ✅ Done | Node dragging (pin/release), zoom +/−/Fit/Reset controls bound via callback ref, click-to-focus neighbours, smoother physics, brand-aligned visual polish. |
| 24 | Rich demo seed data | ✅ Done | `packages/api/scripts/seed_openorg_demo.py` (idempotent) enriches 17 ideas + 7 strategies with schema-valid content; structured rendering in `StrategyDetail`/`IdeaDetail`. |
| 25 | Companies House enricher | ✅ Done | `enrichers/companies_house.py` — governance (officers, filing history, PSC, registered office); filing history → `evidence[]`. |
| 26 | 360Giving API v1 enricher | 🚫 Broken against the real API | Live-tested 2026-07-03 against Trussell Trust (`GB-CHC-1110522`): `fetch_grant_summary` raises an uncaught `AttributeError` (expects `data["grants_received"]["amounts"]`/`is_funder`/`is_grant_recipient`; real API returns `data["recipient"]["aggregate"]["currencies"]["GBP"]`/presence-of-key semantics). `fetch_grants_received`/`fetch_grants_made` don't crash but silently return all-empty `GrantRecord`s — `_parse_grant` reads fields off the wrong nesting level (real grants are under `result["data"]`, not `result` itself). All 19 unit tests pass because they mock the wrong response shape. |
| 27 | MCP server | ✅ Done, not deployed | New `packages/mcp/` package — 7 public tools + 4 resources, stdio + HTTP/SSE. Not wired into `docker-compose.yml`/Caddy yet. Live-tested 2026-07-03 against seeded demo data: `get_themes`, `search_profiles`, `get_profile`, `get_evidence`, `get_graph` all work correctly. |
| 28 | Per-record Murmurations envelopes | ⚠️ Built, unreachable | `build_strategy_envelope()`/`build_idea_envelope()` exist and are unit-tested (28 tests, all mocked), but **nothing calls them** — no API route, no Celery submit task. Confirmed 2026-07-03: `GET /open-org/{org_id}/strategies/{slug}/murmurations.json` 404s to the SPA fallback. Corrected from the earlier "✅ Done" status, which was based on test counts, not reachability. |
| 29 | CRM integrations (Beacon, Lamplight, Salesforce) | ✅ Built, untested live | Pattern A read enrichers (donations/outcomes/grants → `evidence[]`) + Pattern B write methods (`create_constituent` etc.) for one-way push. No credentials provisioned yet — not live-tested; given the 360Giving finding (#26), treat "unit tests pass" as unproven until checked against a real sandbox. |
| 30 | MCP admin tools | ⚠️ Done, one data-integrity bug | `sync_from_crm` (read-only, human-reviewed) — not live-tested (needs CRM creds). `add_evidence` live-tested 2026-07-03: works, but only writes `profile_json` — **does not update `markdown_source`**, breaking the markdown↔JSON round-trip invariant (locked decision #5). Next markdown-editor save on that profile will regenerate `profile_json` from the stale `markdown_source` and silently drop the MCP-added evidence item. |
| 31 | Hypercerts module | ✅ Core module done; ⚠️ no REST API | `open_org/hypercerts.py` (build/mint/fetch/map) + MCP `mint_hypercert` tool exist. Spec's `POST .../mint-hypercert` and `GET .../hypercerts` REST routes were never built. |
| 32 | AT Protocol Lexicon design | ✅ Done (spec only) | `deploy/atprotocol/openorg-lexicons.md` — 6 Lexicons, DID model, hybrid Murmurations/ATProto architecture. Implementation gated on Phase 4 decision; nothing to deploy. |

Status markers: ⏳ not started · 🔧 in progress · ✅ done · 🚫 blocked · ⚠️ needs attention

## Test counts (2026-07-05 session 6, re-verified by running the suites)

| Suite | Count | Notes |
|-------|-------|-------|
| Core (pytest) | 485 | Unchanged count — session 6 repurposed 1 test (theme-extraction failure → success case) rather than adding one |
| MCP (pytest) | 47 | Unchanged this session |
| API (pytest) | 275 | Unchanged — session 6 fixes were core schema/generator + web only |
| Web (vitest) | 217 | Was 216; +1 for the "no false email promise on failed generation" case |
| tsc | clean | |
| eslint | not re-run this session | |

## Data flow (target)

```mermaid
flowchart LR
    CN[Charity number] --> Gen[Profile generator]
    Gen -->|reuses| CC[CC enricher]
    Gen -->|LLM rewrite| Anthro[LLM provider]
    Gen --> MD[markdown_source]
    MD -->|converter| JSON[profile_json]
    JSON --> Public[/open-org/{org_id}/profile.json]
    Public --> Murm[Murmurations index]
    Murm --> Disc[Discovery page — ideas-first]
    Murm --> Graph[Graph view with cluster insights]
    MD --> Editor[Markdown editor]
    Editor -->|save| MD
    Ideas[Published ideas] --> Signals[Funder signals]
    Signals --> Profile[Profile detail — funder interest section]
    Evidence[Evidence items] --> Profile
    History[Version snapshots] --> Timeline[Profile evolution timeline]
```

## Dependencies

| Dependency | Status | Notes |
|---|---|---|
| Postgres 15 | ✅ via docker-compose | |
| Redis 7 | ✅ via docker-compose | |
| Charity Commission API | ✅ key wired | Existing enricher returns full data |
| LLM provider | ✅ Anthropic/OpenRouter/Ollama | Swappable via LLM_PROVIDER/LLM_MODEL env vars |
| Resend (magic links) | ✅ existing | New sender `hello@openorg.good-ship.co.uk` needs domain verification |
| postcodes.io | ✅ wired | Free public API |
| Murmurations index | ✅ test-index default | Flip via env vars when upstream schema PR merges |
| Caddy | ✅ both site blocks configured | `llmstxt.social` + `openorg.good-ship.co.uk` |
| Cloudflare Tunnel | ⚠️ user action | Add route for `openorg.good-ship.co.uk` |
| D3 (graph view) | ✅ installed | `d3` + `@types/d3` added to web package |
| Companies House API | ⚠️ no key provisioned | Enricher built (session 5); no API key in any `.env.example` yet |
| 360Giving API v1 | ✅ no auth needed | Public API, 2 req/sec rate limit |
| Beacon / Lamplight / Salesforce CRM | ⚠️ no credentials provisioned | Enrichers + write clients built (session 5); per-org credential storage not designed yet |
| Hypercerts (Optimism/Ethereum) | ⚠️ no wallet provisioned | Core module + MCP tool built; no custodial wallet key configured, no REST API to trigger minting |
| MCP server (`packages/mcp/`) | ⚠️ not deployed | Package built and tested; no `docker-compose.yml` service, no Caddy route |

## Outstanding user actions

- ~~**Open PR** for `fix/openorg-hardening`~~ — ✅ merged 2026-06-30 (PR #22)
- **Murmurations schema upstream PR** — now 3 schemas drafted at `deploy/murmurations/` (profile, strategy, idea)
- **Cloudflare Tunnel route** for `openorg.good-ship.co.uk`
- **Resend domain verification** for `hello@openorg.good-ship.co.uk`
- **Prod image rebuild + deploy** — stale image needs rebuild (new `openai` dep + D3 dep + `@fontsource-variable/dm-sans`)
- **Editor polish PR 7** (keyboard + motion polish) — still outstanding
- **Decide on Phase 2 branch review** — `feat/phase2-federation-evidence` merged straight to `origin/master` with no PR opened
- **Provision + document Phase 2 credentials** — Companies House API key, Beacon/Lamplight/Salesforce credentials, Hypercerts custodial wallet key
- **Decide MCP server deployment** — add a `docker-compose.yml` service + Caddy route, or keep local-only
- **Decide on Hypercerts REST API** — build the spec's `mint-hypercert`/`hypercerts` routes, or leave minting MCP-only for now
- **Commit or discard `open-org/open-org-phase2-spec.md`** — currently untracked
- **[Session 6] Decide on the stray `GB-CHC-1001635` (NAVCA) row in production** — `generation_status: failed` from before this session's fix
- **[Session 6] Resolve duplicate `worker`/`beat` vs `celery_worker`/`celery_beat` on `llmstxt-local`** — deliberate stop/rm needed, see `MISTAKES.md`
- **[Session 6] Review and commit 14 uncommitted files on `master`** — see `HANDOFF.md` session 6 for the full list and rationale

## Essay vision gap analysis

Assessed against [the essay](https://tomcw.xyz/the-grant-application-is-dead-what-comes-next/). 10 gaps identified, 8 addressed:

| # | Gap | Status |
|---|-----|--------|
| 1 | Evidence layer is empty | ✅ Done — top-level `evidence` array, converter, profile detail display, now populated by CH/360Giving/CRM enrichers |
| 2 | Culture is thin | ✅ Schema has `culture.narrative` + `values` array; content depends on orgs |
| 3 | No funder signalling | ✅ Done — OrgSignal model, 3 API endpoints, SignalButton, FunderInterestSection |
| 4 | No access control / audit trail | ⏳ Moved to a separate "Phase 2.5" spec. OrgVersion audit trail exists; tiered access control is not built. |
| 5 | No local agent / evidence integration | ✅ Done (session 5) — CRM enrichers + MCP `sync_from_crm`/`add_evidence` tools; agent is conversation-driven (human reviews before write), not a background daemon |
| 6 | No profile evolution / trajectory | ✅ Done — version history API, timeline on profile detail, status badges |
| 7 | No funder-facing view | ⏳ Not started. Ideas-first discovery partly addresses this. |
| 8 | No temporal dimension | ✅ Partly done — timeline shows change over time |
| 9 | Cluster insights not described meaningfully | ✅ Done — org names, ideas summary, places, dominant themes, human-readable descriptions |
| 10 | Ideas not centred in discovery | ✅ Done — ideas-first default view, hero summary, theme chips, filters, sort |