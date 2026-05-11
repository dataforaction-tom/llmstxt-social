# State

> Last updated: 2026-05-11
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
    Live --> [*]

    note right of Testing: ← WE ARE HERE (v0.2 baselined; 5/6 must-pass green; v0.2.6 crawler tweaks queued)
```

## Component status

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 0 | Schemas + theme vocab + validator | ✅ Done | 30-theme vocab, three v0.1 schemas, jsonschema-Draft202012 validator wrapper, full TDD coverage |
| 1 | Markdown ↔ JSON converter | ✅ Done | Round-trip identity asserted; profile/strategy/idea section maps; deferred priorities/relationships body-rendering to v0.2 |
| 2 | DB models + Alembic migration | ✅ Done | 8 models with structural tests; migration b1c2d3e4f5a6; ready for `alembic upgrade head` |
| 3 | CachedAnthropic + llm_usage logging | ✅ Done | Cached system blocks, sync complete + stream, USD/GBP pricing, £0.50/day cap helper |
| 4 | Markdown editor UI + magic-link auth | ⚠️ Partial | Backend complete (10 routes); frontend has textarea editor + TanStack Query hooks. CodeMirror/Vitest/strategy+idea pages deferred. |
| 5 | Profile generator | ✅ Done | Orchestrator + ONS lookup + theme extractor + mission rewriter + claim flow + `POST /api/open-org/generate` + Celery task. 229 tests green; migration `c2d3e4f5a6b7` up/down/up clean. |
| 6 | Murmurations schema upstream PR | ⚠️ User action needed | Schema + reference profile drafted at `deploy/murmurations/`; user opens PR to MurmurationsNetwork/MurmurationsLibrary |
| 7 | Murmurations connector + postcodes.io | ✅ Done | postcodes.io enricher + LAD centroid + envelope + client + public /murmurations.json + publish route + submit task + daily cache sync. Defaults to test-index; flip via env vars when upstream schema PR merges. |
| 8 | Strategy/idea chat creator | ✅ Done | Prompts + PDF/DOCX/TXT extractors + conversation orchestrator + SSE routes (create / message / finalize / get) + £0.50/org/day cap. Auto-extends frontend prompt via `update_current_markdown` tool. |
| 9 | Discovery page | ✅ Done | `GET /api/open-org/themes` + `GET /api/open-org/discover` (cursor pagination, union of `OrgProfile` + `ExternalOrgCache`). React page at `/openorg/discover` with Leaflet map, filter form, "Load more". |
| 10 | Subdomain routing + Caddy | ✅ Done | Caddyfile with two site blocks (llmstxt.social + openorg.good-ship.co.uk); env-driven `AUTH_COOKIE_DOMAIN` for cross-subdomain cookies; host-aware `HostRoot` redirects openorg.* root to `/openorg/discover`. Cloudflare Tunnel route is a user action. |
| 11 | Real-world testing harness | ✅ Done + baselined | `core/open_org/harness.py` + `llmstxt openorg test-corpus` CLI. v0.1 baseline run on 2026-05-11 against 10 UK charities; report committed at `tests/reports/baseline_v0.1.md`. Findings drive Phase 1.5 (see PLAN.md). |

Status markers: ⏳ not started · 🔧 in progress · ✅ done · 🚫 blocked · ⚠️ needs attention

## Data flow (target)

```mermaid
flowchart LR
    CN[Charity number] --> Gen[Profile generator]
    Gen -->|reuses| CC[CC enricher]
    Gen -->|LLM rewrite| Anthro[CachedAnthropic]
    Gen --> MD[markdown_source]
    MD -->|converter| JSON[profile_json]
    JSON --> Public[/open-org/{org_id}/profile.json]
    Public --> Murm[Murmurations index]
    Murm --> Disc[Discovery page]
    MD --> Editor[Markdown editor]
    Editor -->|save| MD
```

## Dependencies

| Dependency | Status | Notes |
|---|---|---|
| Postgres 15 | ✅ via docker-compose | |
| Redis 7 | ✅ via docker-compose | |
| Charity Commission API | ✅ key wired in `settings.charity_commission_api_key` | Existing enricher returns full data |
| Anthropic API | ✅ key wired in `settings.anthropic_api_key` | Sync client today; introducing CachedAnthropic in Step 3 |
| Resend (magic links) | ✅ existing | New sender `hello@openorg.good-ship.co.uk` needs domain verification |
| postcodes.io | ✅ wired in `enrichers/postcodes_io.py` | Free public API; called from Murmurations envelope builder |
| Murmurations index | ✅ test-index default; flip via env vars when Step 6 PR merges | `MURMURATIONS_INDEX_URL` / `MURMURATIONS_LIBRARY_URL`; defaults to test-index |
| ONS Linked Data API | ⏳ fallback for LAD code lookup | Local table covers ~90% |
| Caddy (deploy/caddy/Caddyfile) | ✅ both site blocks configured | `llmstxt.social` + `openorg.good-ship.co.uk` both reverse-proxy to `localhost:8000` |
| Cloudflare Tunnel | ⚠️ managed outside repo | User adds route via `cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk` (or Zero Trust UI) |
