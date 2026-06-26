# State

> Last updated: 2026-06-25 (session 2)
> See `HANDOFF.md` for the full session wrap-up and resume instructions.

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
    Vision --> [*]: branch pushed, PR pending, ideas-first discovery test in progress

    note right of Vision: ← WE ARE HERE (22 commits on fix/openorg-hardening, pushed; ideas-first discovery API done, frontend test pending)
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
| 20 | Ideas-first discovery | 🔧 In progress | API done (summary endpoint + sort param). Frontend Discover.tsx rewritten. Test file has leaflet mock issue — `vi.mock('leaflet')` needs `default` export key. API tests pass (264). Frontend test pending fix. |

Status markers: ⏳ not started · 🔧 in progress · ✅ done · 🚫 blocked · ⚠️ needs attention

## Test counts (2026-06-25 session 2)

| Suite | Count | Notes |
|-------|-------|-------|
| Core (pytest) | 325 | Was 314; +11 evidence converter tests |
| API (pytest) | 264 | Was 216; +11 funder signal tests, +8 ideas summary/sort tests, +29 other new tests |
| Web (vitest) | 200 | Was 171; +5 cluster tests, +4 evolution tests, +5 evidence tests, +4 signal tests, +11 other. Discover.test.tsx not yet passing (pending leaflet mock fix) |
| tsc | clean | |
| eslint | clean | |

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

## Outstanding user actions

- **Open PR** for `fix/openorg-hardening` → https://github.com/dataforaction-tom/llmstxt-social/pull/new/fix/openorg-hardening
- **Murmurations schema upstream PR** — schema drafted at `deploy/murmurations/`
- **Cloudflare Tunnel route** for `openorg.good-ship.co.uk`
- **Resend domain verification** for `hello@openorg.good-ship.co.uk`
- **Prod image rebuild + deploy** — stale image needs rebuild (new `openai` dep + D3 dep + `@fontsource-variable/dm-sans`)
- **Editor polish PR 7** (keyboard + motion polish) — still outstanding

## Essay vision gap analysis

Assessed against [the essay](https://tomcw.xyz/the-grant-application-is-dead-what-comes-next/). 10 gaps identified, 6 addressed:

| # | Gap | Status |
|---|-----|--------|
| 1 | Evidence layer is empty | ✅ Done — top-level `evidence` array, converter, profile detail display |
| 2 | Culture is thin | ✅ Schema has `culture.narrative` + `values` array; content depends on orgs |
| 3 | No funder signalling | ✅ Done — OrgSignal model, 3 API endpoints, SignalButton, FunderInterestSection |
| 4 | No access control / audit trail | ⏳ Phase 2 per spec. OrgVersion audit trail exists; proper access control is Phase 2. |
| 5 | No local agent / evidence integration | ⏳ Phase 2 per spec |
| 6 | No profile evolution / trajectory | ✅ Done — version history API, timeline on profile detail, status badges |
| 7 | No funder-facing view | ⏳ Not started. Ideas-first discovery partly addresses this. |
| 8 | No temporal dimension | ✅ Partly done — timeline shows change over time |
| 9 | Cluster insights not described meaningfully | ✅ Done — org names, ideas summary, places, dominant themes, human-readable descriptions |
| 10 | Ideas not centred in discovery | 🔧 In progress — API done, frontend written, test pending |