# Open Org Phase 2 — Federation, Evidence, and System Integration

> Drafted: 2026-07-03
> Status: **Draft — for review**
> Depends on: Phase 1 complete (✅), Phase 1.5 theme extraction complete (✅), PR #22 merged
> Spec: `open-org/open-org-phase1-spec.md` (Phase 1)
> Essay: https://tomcw.xyz/the-grant-application-is-dead-what-comes-next/
> Resume guide: `HANDOFF.md`

## Purpose

Phase 1 proved the data model works: a charity number becomes a published, federated, machine-readable profile with strategies, ideas, evidence, and funder signalling. Phase 1.5 closed the theme-extraction gaps.

Phase 2 connects Open Org to the wider ecosystem — the systems charities already use, the data sources that enrich profiles, the federation layers that make profiles portable, and the on-chain primitives that let organisations claim impact. The essay's thesis is that the grant application is dead; what replaces it is a living, machine-readable organisation profile that funders, partners, and the org itself can all read and write to. Phase 2 builds the connective tissue.

Five workstreams:

1. **Evidence enrichers** — automated data pulls that populate the `evidence[]` array
2. **CRM integration via agent** — read/write sync between Open Org and the systems charities actually use
3. **MCP server** — expose Open Org data and operations to any AI agent
4. **Federation evolution** — Murmurations hardening + AT Protocol path
5. **Impact linking to Hypercerts** — on-chain impact claims from CRM outcome data

## What Phase 2 builds (and doesn't)

**Builds:**
- New enrichers (Companies House, 360Giving API v1)
- CRM agent integration (Beacon, Lamplight, Salesforce, Donorfy)
- `openorg-mcp-server`
- Murmurations upstream merge + per-record submission
- AT Protocol Lexicon design (spec only — implementation gated on Phase 4 decision)
- Hypercerts impact-claim pipeline (CRM outcomes → evidence → mint)

**Doesn't build:**
- Access control / tiered permissions (remains Phase 2.5 — separate spec)
- Strategy matching / cluster detection (Phase 3)
- Funder profiles (Phase 3)
- Full AT Protocol PDS/relay/App View deployment (Phase 4 — this spec designs the Lexicons and migration path only)
- Firecrawl crawler tier (held — not needed for current corpus)

---

## Workstream 1 — Evidence Enrichers

### Context

The `evidence[]` array in `org_profile.schema.json` has the right shape (evidence_id, title, evidence_type, date, url, themes, outcomes) and the converter round-trips it. But no enricher populates it — the only evidence-adjacent field is the lightweight `mission.evidence_summary` stub populated from the website analyzer's `impact_metrics`.

### 1.1 — Companies House enricher

**What:** New `packages/core/src/llmstxt_core/enrichers/companies_house.py`.

**Why:** Most medium+ UK charities are companies limited by guarantee. Companies House holds governance data (registered office, officers/directors, PSC/beneficial ownership, filing history, accounts) that the Charity Commission doesn't. The CC enricher already extracts `company_number` — that's the bridge.

**API:** REST at `api.company-information.service.gov.uk`, HTTP Basic auth with API key. OpenAPI spec at `developer-specs.company-information.service.gov.uk`. Rate limit 600 req/5min.

**Scope:**
- `get_company_profile(company_number)` → registered office, company status, type, accounts.next_due, sic_codes
- `get_officers(company_number)` → directors/trustees (name, role, appointed_on, resigned_on)
- `get_filing_history(company_number)` → annual returns, accounts filings (date, type, description)
- `get_psc(company_number)` → persons with significant control

**Integration point:** `generator.py` calls CC enricher → extract `company_number` → call CH enricher → populate `governance` fields in profile JSON. Filing history becomes `evidence[]` items (`evidence_type: "annual_report"`, `url` to filing document).

**Schema additions:**
- `governance.company_status` (string)
- `governance.filing_history` (array of {date, type, description, url})
- `governance.officers` (array of {name, role, appointed_on, resigned_on?})
- `governance.psc` (array of {name, nature_of_control})

**Tests:** Mock HTTP (same pattern as `charity_commission.py`). Filing history → evidence mapping tested. Company-not-found degradation (empty result, doesn't break generation).

### 1.2 — 360Giving API v1 enricher

**What:** Rewrite `packages/core/src/llmstxt_core/enrichers/threesixty_giving.py` to use the new REST API instead of the bulk-file/registry pattern.

**Why:** The current enricher downloads entire publisher datasets. The new API (2024) at `api.threesixtygiving.org/api/v1/` lets you query by org_id directly — the same `GB-CHC-{number}` scheme Open Org already generates. No auth required, 2 req/sec rate limit.

**API endpoints:**
- `GET /org/{org_id}/` → funder/recipient flag, aggregate grant stats (count, avg/min/max/total per currency)
- `GET /org/{org_id}/grants_made/` → paginated grants this org has awarded
- `GET /org/{org_id}/grants_received/` → paginated grants this org has received

**Scope:**
- `get_grant_summary(org_id)` → aggregate stats (total received, total awarded, count, avg, date range)
- `get_grants_received(org_id, limit=50)` → individual grant records (funder, amount, date, title, description)
- `get_grants_made(org_id, limit=50)` → grants this org has awarded

**Integration point:** `generator.py` calls after CC enricher. Grant summary → new `funding_history` section in profile JSON. Individual grants → `evidence[]` items (`evidence_type: "outcome_data"`, `url` to GrantNav record, `themes` mapped from grant titles/subjects).

**Schema additions:**
- `funding_history.total_received` (number, GBP)
- `funding_history.total_awarded` (number, GBP)
- `funding_history.grant_count` (integer)
- `funding_history.grants[]` (array of {funder, amount, date, title, url})

**Tests:** Mock HTTP. Rate-limit handling (2 req/sec). Empty-result degradation (org with no grants → field omitted, not empty array).

### 1.3 — URL-citation evidence (agent-assisted)

**What:** Not an enricher — a workflow. The local agent (Workstream 2) or a human editor adds evidence items by URL. The schema already supports this.

**Sources:**
- J-PAL evaluations → `evidence_type: "external_research"`
- 3ie systematic reviews / Evidence Gap Maps → `evidence_type: "external_research"`
- Published SROI reports (Social Value UK reports database) → `evidence_type: "external_research"`
- B Corp profiles → `evidence_type: "external_research"`
- Annual reports (from Companies House filings) → `evidence_type: "annual_report"`

**No API needed.** The agent reads the URL, extracts title/date/summary, maps themes to the controlled vocabulary, and writes a structured `evidence[]` item. The converter already round-trips `### {evidence_id}: {title}` markdown subsections.

**Scope:** Agent prompt + extraction logic (part of Workstream 2/3). No new enricher module.

---

## Workstream 2 — CRM Integration via Agent

### Context

Charities live in their CRM. If Open Org profiles can't read from and write to the CRM, they're another silo. The agent pattern: an AI agent sits between Open Org and the CRM, mapping fields, syncing changes, and using the CRM's outcome/impact data to populate evidence and (via Workstream 5) mint Hypercerts.

### 2.1 — CRM landscape

| CRM | API | Focus | Outcome/impact data | UK market |
|-----|-----|-------|---------------------|-----------|
| **Beacon CRM** | REST API, API key | Fundraising + case management | Some (case management module) | ✅ UK-native, 1,000+ orgs, #1 rated, ISO 27001 |
| **Lamplight** | Publishing API (paid module) + Data Connect (read-only OData) | **Service delivery + outcomes** | ✅ Core — WEMWBS, Outcome Stars, CORE, PHQ6, GAD7, custom outcome measurements tracked over time | ✅ UK-native, 700+ orgs, Lloyds Bank Foundation preferred, ISO 27001 |
| **Salesforce Nonprofit Cloud** | REST API + OAuth2, Agentforce MCP support coming | Fundraising + programs + grants | Configurable (custom objects) | Large orgs, 10 free licenses |
| **Donorfy** | REST (legacy, being rebuilt with bulk ops + change tracking) | Fundraising | Limited | UK, Access Group |
| **CiviCRM** | REST API v3/v4, open-source | General CRM | Configurable | Self-hosted, free |
| **Raisely** | RESTful JSON + webhooks | Fundraising campaigns | No | Smaller orgs |

### 2.2 — Priority integrations

**Beacon** — best UK-native API, fundraising + case management. REST API with API key auth. Can read constituents, donations, campaigns, cases. Write path: create/update constituent records from Open Org profile data.

**Lamplight** — the only CRM where outcomes/impact is the core data model, not an add-on. Holds work records (sessions, casework), outcome measurements (WEMWBS, Outcome Stars, CORE, PHQ6, GAD7, custom — repeat measurements over time), referrals, evaluations, attendance, safeguarding. This is exactly the data needed for evidence items and Hypercerts impact claims.

Lamplight API constraints:
- API is gated behind two paid add-on modules (Publishing Module for writes, Data Connect for reads)
- No public API docs (behind login), no webhooks, no Zapier, no developer ecosystem
- Publishing API can create profiles, relationships, waiting list entries, accept referrals/bookings — outcome record write path unconfirmed
- Data Connect provides read-only OData feed (Power BI/Excel) — viable for reading outcome data out
- **Approach:** read-first via Data Connect, contact Lamplight for Publishing API docs access, pilot with a charity already using Lamplight

**Salesforce Nonprofit Cloud** — for larger orgs. Building native MCP support (Agentforce). REST API + OAuth2. Custom objects for outcomes are configurable. The Salesforce → MCP path is the most forward-looking: if Salesforce ships Agentforce MCP, the agent can talk to Salesforce natively without a custom integration layer.

### 2.3 — Agent architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Open Org   │────▶│   AI Agent +     │────▶│  CRM        │
│  Profiles   │     │   MCP Server     │     │  (Beacon,   │
│  (JSON)     │◀────│                  │◀────│  Lamplight, │
└─────────────┘     └──────────────────┘     │  Salesforce)│
                           │                  └─────────────┘
                    ┌──────┴──────┐
                    │  Data Sources│
                    │  CC API      │
                    │  Companies H │
                    │  360Giving   │
                    └─────────────┘
```

The agent is not a background daemon. It's a **conversation-driven workflow** — a charity admin opens the Open Org editor, the agent (via MCP tools) reads the CRM, maps relevant data to the profile schema, and suggests changes. The human reviews and approves. This matches the essay's framing: the org owns its profile, the agent helps maintain it.

### 2.4 — Sync patterns (build in order)

**Pattern A — Read-only enrichment (first):**
Agent reads CRM (Beacon/Lamplight/Salesforce) → extracts outcome data, grant history, beneficiary numbers → maps to `evidence[]` items and profile fields → writes to Open Org → human reviews.

**Pattern B — One-way push:**
Agent reads Open Org profile → maps to CRM schema → pushes via REST API. "Your Open Org profile says you run food access programmes in Great Yarmouth — created a tag in Beacon."

**Pattern C — Bidirectional sync:**
Agent monitors both. CRM outcome measurement updated → suggests evidence update in Open Org. Open Org strategy published → creates a campaign record in CRM. Requires change tracking (Donorfy new API, Salesforce, Beacon polling).

### 2.5 — Field mapping

Each CRM needs a mapping layer. Open Org's schema is flatter and more semantic; CRMs are relational and operationally structured.

**Open Org → Beacon:**
- `identity.name` → constituent.name
- `identity.identifiers.org_id` → constituent.charity_number (custom field)
- `mission.themes` → tags
- `ideas[]` → campaigns (title, description, status)
- `evidence[]` → case records (linked to constituent)

**Open Org → Lamplight:**
- `identity.name` → profile.name
- `mission.themes` → service tags
- `evidence[]` (outcome_data type) → outcome measurements (WEMWBS, Outcome Star, custom)
- `ideas[]` → work records / projects
- `evidence[].outcomes` → outcome scores

**Open Org → Salesforce:**
- `identity` → Account
- `ideas[]` → Opportunities (custom record type)
- `evidence[]` → Custom Object (Evidence__c)
- `mission.themes` → Topics/Tags

The mapping lives in `packages/core/src/llmstxt_core/open_org/crm_mappings/` — one module per CRM, each exposing `crm_to_evidence(crm_record)` and `profile_to_crm(profile_json)`.

---

## Workstream 3 — MCP Server

### Context

No MCP server exists for UK charity data. Open Org already uses Claude as its LLM provider and has Claude skills (`/org-strategy`, `/org-idea`). An MCP server makes Open Org's data and operations available to any MCP-compatible client — Claude Desktop, Cursor, custom agents, other CRMs' AI features (Salesforce Agentforce).

### 3.1 — Server design

**Package:** `packages/mcp/` (new package in the monorepo).

**Transport:** stdio (local, for Claude Desktop/CLI) + HTTP/SSE (remote, for cloud agents).

**Tools:**

| Tool | Description | Auth |
|------|-------------|------|
| `get_profile` | Fetch an org's full profile JSON by org_id | Public (published profiles) |
| `search_profiles` | Search by theme, place, name, status | Public |
| `get_ideas` | List ideas for an org | Public |
| `get_strategies` | List strategies for an org | Public |
| `get_evidence` | List evidence items for an org | Public |
| `get_graph` | Discovery graph data | Public |
| `enrich_from_companies_house` | Pull CH data for an org | Admin (org admin token) |
| `enrich_from_360giving` | Pull grant history | Admin |
| `sync_from_crm` | Pull outcome/donor data from configured CRM | Admin |
| `sync_to_crm` | Push profile updates to CRM | Admin |
| `add_evidence` | Add an evidence item (URL citation or structured) | Admin |
| `mint_hypercert` | Mint an on-chain impact claim from evidence | Admin |
| `generate_strategy` | Start a strategy creation session | Admin |
| `generate_idea` | Start an idea creation session | Admin |

**Resources:**
- `openorg://orgs/{org_id}/profile` — full profile JSON
- `openorg://orgs/{org_id}/ideas/{slug}` — individual idea
- `openorg://orgs/{org_id}/strategies/{slug}` — individual strategy
- `openorg://orgs/{org_id}/evidence` — evidence array
- `openorg://themes` — controlled vocabulary
- `openorg://discover/graph` — graph data

**Prompts:**
- `org-strategy-guide` (from existing Claude skill)
- `org-idea-guide` (from existing Claude skill)
- `grant-readiness-check` — assess profile completeness for funder discovery
- `evidence-review` — review evidence items and suggest gaps
- `crm-sync-review` — review what would change in a CRM sync before approving

### 3.2 — Implementation

Python MCP server using the `mcp` SDK (or `fastmcp` for a FastAPI-style DX). Shares the Open Org database session and core modules. Lives in the same monorepo, same Docker stack.

```python
# packages/mcp/src/openorg_mcp/server.py
from mcp.server import Server
from mcp.types import Tool, Resource, Prompt

server = Server("openorg")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="get_profile", ...),
        Tool(name="sync_from_crm", ...),
        Tool(name="mint_hypercert", ...),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    # Route to Open Org core modules
    ...
```

**Config:** `MCP_TRANSPORT` (stdio|http), `MCP_HTTP_PORT` (default 8001). Runs as a separate Docker service in `docker-compose.yml`.

### 3.3 — Security

- Public tools (read) need no auth
- Admin tools require an org admin token (same magic-link auth, passed as MCP auth header)
- CRM sync tools require CRM credentials in env vars per org (encrypted at rest)
- `mint_hypercert` requires explicit confirmation prompt (on-chain action, irreversible)

---

## Workstream 4 — Federation Evolution

### 4.1 — Murmurations hardening (ship now)

**Upstream PR:** The schema (`open_org_profile-v0.1.0`), reference profile, and README are drafted at `deploy/murmurations/`. User opens the PR to `MurmurationsNetwork/MurmurationsLibrary`. Until merged, build runs against test-index.

**Per-record submission (Phase 2):** Phase 1 submits only the profile envelope. Phase 2 adds strategy and idea schemas to Murmurations:
- `open_org_strategy-v0.1.0.json` — strategy fields (themes, priorities, relationships, funding_mix, learning)
- `open_org_idea-v0.1.0.json` — idea fields (summary, themes, cost_range, status, evidence_refs)
- `build_envelope()` extended to produce per-record envelopes
- New Celery tasks: `submit_strategy_task`, `submit_idea_task`
- `GET /open-org/{org_id}/strategies/{slug}/murmurations.json` + `GET /open-org/{org_id}/ideas/{slug}/murmurations.json`

**Discovery federation:** The `sync_external_org_cache_task` already pulls federated profiles. Extend to pull strategies and ideas from other nodes running the Open Org schemas. Discovery page shows federated strategies/ideas alongside local ones.

### 4.2 — AT Protocol Lexicon design (spec only — implementation gated on Phase 4)

**Why design now:** The schema and data model are stable. Lexicons map directly to the existing JSON schemas. Designing them now means the migration path is clear and the decision to build (or not) in Phase 4 is informed.

**Lexicons:**

```
uk.co.goodship.openorg.profile      — record (maps to org_profile.schema.json)
uk.co.goodship.openorg.strategy      — record (maps to org_strategy.schema.json)
uk.co.goodship.openorg.idea          — record (maps to org_idea.schema.json)
uk.co.goodship.openorg.evidence      — record (maps to evidence[] items)
uk.co.goodship.openorg.signal        — record (maps to OrgSignal — funder interest)
uk.co.goodship.openorg.defs          — shared shapes (themes, income_bands, org_id)
```

**Identity model:**
- Each org gets a DID. Two options:
  - `did:plc:{id}` — Bluesky's PLC directory, rotation keys for portability. Requires PLC account.
  - `did:web:openorg.good-ship.co.uk:{org_id}` — DNS-based, simpler, no PLC dependency. Good Ship controls the domain.
- Handle: `{org_id}.openorg.good-ship.co.uk` (or a custom domain the org owns)

**Migration path (Phase 4 build):**
1. Good Ship runs a PDS (or uses a hosted one like Bluesky's, or `atproto.com`'s)
2. Each published profile is mirrored as an AT Protocol record in the org's repo
3. A relay subscribes to `uk.co.goodship.openorg.*` collections
4. An App View indexes records, serves the discovery page + graph
5. Auth transitions from magic links to OAuth (atproto's OAuth flow) — org admins authorize the Open Org app to write records
6. Murmurations stays as a thin discovery index — the AT Proto relay can feed it

**Hybrid architecture:**

```
                    ┌─────────────────┐
                    │   Murmurations   │
                    │   (discovery     │
                    │    index)        │
                    └────────┬────────┘
                             │
┌─────────┐         ┌────────┴────────┐         ┌──────────┐
│  PDS    │────────▶│     Relay        │────────▶│ App View │
│ (org    │  fire   │ (subscribes to   │  index  │ (search, │
│  repos) │  hose   │  openorg.*       │         │  graph)  │
└─────────┘         └─────────────────┘         └──────────┘
```

Murmurations = pull-based discovery for aggregators that don't want a relay. AT Proto = push-based real-time federation with signed, portable records. Both can coexist. The Murmurations envelope can be generated from the AT Protocol record.

**Decision gate:** Build AT Protocol layer in Phase 4 only if:
- Orgs express demand for profile portability (moving away from Good Ship)
- The ecosystem matures (community Lexicon discovery, hosted PDS options)
- Murmurations hits scaling limits

### 4.3 — What we don't do in Phase 2

- Don't run a PDS, relay, or App View
- Don't migrate auth to OAuth
- Don't change the existing Murmurations integration (just extend it)
- Don't build ActivityPub bridge (Murmurations has their own AP exploration — not our problem)

---

## Workstream 5 — Impact Linking to Hypercerts

### Context

Hypercerts are on-chain impact-claim tokens (Ethereum) representing "a discrete piece of work and impact." An org does work → mints a hypercert → the hypercert is evidence of impact that funders can verify. The `evidence[]` schema already references Hypercerts in its description.

The missing link is the pipe between "we measured an outcome in our CRM" and "we minted a hypercert that represents that impact." This workstream builds that pipe.

### 5.1 — The impact pipeline

```
CRM outcome data          Open Org evidence           Hypercert
(Lamplight, Beacon,       (evidence[] items,          (on-chain token)
 Salesforce)               structured + verified)
        │                         │                         │
        ▼                         │                         │
  Agent extracts                  │                         │
  outcome measurement             │                         │
  (WEMWBS score, Outcome          │                         │
  Star, custom metric)            │                         │
        │                         │                         │
        ▼                         │                         │
  Maps to evidence[] ──────────────┘                         │
  item (evidence_type:                                            │
   "outcome_data", themes,                                       │
   outcomes, date, url)                                          │
        │                                                        │
        ▼                                                        │
  Agent + admin review ──────────────────────────────────────────┘
  (confirm impact claim
   is accurate)
        │
        ▼
  Mint hypercert
  (work scope, impact
   scope, contributors,
   dates, evidence ref)
```

### 5.2 — Hypercerts protocol integration

**Protocol:** Hypercerts on Ethereum (currently Optimism mainnet). ERC-1155 semi-fungible tokens. Each token represents a unit of impact work.

**Contract:**
- Mint: `mint(bytes32 scope, bytes32[] work, bytes32[] impact, uint256 units, bytes32[] contributors, uint256[] timeframe)`
- Read: query the Hypercerts subgraph (The Graph) by contributor address or claim hash
- Transfer: standard ERC-1155 transfers (fractional ownership of impact claims)

**Integration scope:**
- `packages/core/src/llmstxt_core/open_org/hypercerts.py` — new module
  - `build_claim(evidence_item, org_id)` → constructs the on-chain claim data (work scope, impact scope, contributors, timeframe, units) from a verified evidence item
  - `mint_claim(claim_data, wallet)` → submits mint transaction (requires an Ethereum wallet — org's or Good Ship's custodial)
  - `fetch_hypercerts_for_org(org_id)` → queries subgraph for hypercerts attributed to this org
  - `hypercert_to_evidence(hypercert)` → maps a fetched hypercert back to an `evidence[]` item
- `packages/mcp/src/openorg_mcp/server.py` — `mint_hypercert` tool (admin-only, explicit confirmation prompt)
- `packages/api/src/llmstxt_api/routes/open_org_hypercerts.py` — API routes
  - `POST /api/open-org/{org_id}/evidence/{evidence_id}/mint-hypercert` — mint from a verified evidence item
  - `GET /open-org/{org_id}/hypercerts` — public list of minted hypercerts
  - `GET /open-org/{org_id}/hypercerts/{token_id}` — individual hypercert detail

**Schema additions:**
- `evidence[].hypercert` — { token_id, chain_id, contract_address, mint_date, units } — links an evidence item to its on-chain token
- `profile.hypercerts[]` — array of { token_id, claim_hash, work_scope, impact_scope, units, contributors, timeframe, url }

**Wallet model:**
- Phase 2: Good Ship custodial wallet (private key in env var, encrypted). Orgs don't need their own wallet to mint.
- Phase 3: org-owned wallets (org admin connects MetaMask / WalletConnect, signs transactions themselves)

**Agent role:**
The agent is central to this pipeline. It:
1. Reads CRM outcome data (Lamplight WEMWBS scores, Beacon case outcomes, Salesforce custom objects)
2. Extracts the measurement: "30 beneficiaries, average WEMWBS improvement +8.2 over 6 months, food_access theme"
3. Structures it as an `evidence[]` item with `evidence_type: "outcome_data"`, `outcomes: [{metric, baseline, follow_up, change, n}]`, `themes: ["food_access"]`
4. Presents to the admin: "This outcome measurement could become a hypercert. Here's the claim: [work scope, impact scope, units]. Mint?"
5. Admin confirms → agent calls `mint_hypercert` MCP tool → transaction submitted → token ID stored in evidence item
6. Hypercert appears in the public profile and on the Hypercerts registry

**Why this matters:**
This is the essay's thesis made concrete. The grant application is replaced by: org does work → CRM records outcomes → agent structures as evidence → org mints hypercert → funder discovers via Murmurations/ATProto → funder can verify the impact claim on-chain. No application form. No PDF. No 6-month wait. The living profile IS the application.

### 5.3 — Security and trust

- **Evidence verification:** Before minting, the agent cross-references the CRM data source (not just the evidence item). The hypercert's `contributors` field includes the CRM system identity ("Lamplight:org-123") as a provenance chain.
- **Admin confirmation:** Minting is irreversible (on-chain). The MCP tool requires explicit confirmation with a summary of what will be minted.
- **No over-claiming:** The agent prompt includes guardrails: "Only mint hypercerts for outcomes with measured data. Do not mint for aspirations or plans." The evidence item must have `evidence_type: "outcome_data"` and populated `outcomes[]`.
- **Public verifiability:** `GET /open-org/{org_id}/hypercerts` is public. Anyone can verify the on-chain token and trace it back to the evidence item and CRM source.

---

## Build order

Dependency-ordered, not time-ordered. Each step is a green-test-commit cycle.

```
Step 1   Companies House enricher                    (evidence, no deps)
Step 2   360Giving API v1 rewrite                    (evidence, no deps)
Step 3   openorg-mcp-server (public tools only)      (MCP, no deps)
Step 4   Murmurations per-record schemas + submit    (federation, no deps)
Step 5   Beacon CRM integration (Pattern A — read)   (CRM, depends on Step 3)
Step 6   Lamplight CRM integration (read via Data    (CRM, depends on Step 3)
         Connect, write via Publishing API)
Step 7   Salesforce CRM integration (Pattern A)      (CRM, depends on Step 3)
Step 8   MCP admin tools (sync_from_crm, add_evidence)(MCP + CRM, depends on 3, 5-7)
Step 9   Hypercerts module + mint pipeline           (impact, depends on Step 8)
Step 10  MCP mint_hypercert tool                     (impact, depends on 9)
Step 11  AT Protocol Lexicon design (spec only)      (federation, no deps)
Step 12  CRM Pattern B — one-way push                (CRM, depends on 8)
```

Steps 1-4 can run in parallel. Steps 5-7 can run in parallel. Step 9 is the capstone — it connects CRM outcome data to on-chain impact claims via the agent + MCP.

---

## Locked decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | No CharityBase integration | User decision. CC + Companies House + 360Giving direct enrichers instead of aggregator. |
| 2 | MCP server in the monorepo | Shares DB session, core modules, Docker stack. Same deploy unit. |
| 3 | Lamplight: read-first via Data Connect, vendor engagement for writes | API is gated behind paid modules with no public docs. Don't assume write capabilities until confirmed. |
| 4 | Good Ship custodial wallet for Phase 2 hypercert minting | Orgs don't need wallets to participate. Phase 3 transitions to org-owned wallets. |
| 5 | AT Protocol: design Lexicons now, build in Phase 4 only | Schema is stable; Lexicons map directly. But PDS/relay/App View is operational burden that needs ecosystem maturity and user demand to justify. |
| 6 | Murmurations stays as discovery index even if AT Protocol is built | Hybrid architecture. Murmurations for pull-based aggregators, ATProto for signed/portable/real-time. Both coexist. |
| 7 | Agent is conversation-driven, not a background daemon | Matches the essay's framing: org owns its profile, agent helps maintain it. Human reviews before any write (especially minting). |
| 8 | CRM field mappings live in `packages/core/`, one module per CRM | Keeps mappings testable and swappable. Not in the MCP server — the MCP server calls the mapping modules. |
| 9 | Per-record Murmurations submission in Phase 2 | Strategies and ideas should be federated, not just profiles. Schema extension is straightforward. |
| 10 | Hypercert minting requires `evidence_type: "outcome_data"` with populated `outcomes[]` | No minting for aspirations or plans. Only verified, measured impact. |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Lamplight API access gated behind paid modules + no public docs | Read-first via Data Connect. Contact Lamplight directly. Pilot with a charity already using it. Don't block other CRM integrations on Lamplight. |
| Hypercerts protocol changes (still evolving) | Use the published contract interface. Pin to a specific contract address. Schema field is versioned. |
| Companies House API rate limits (600/5min) | Cache responses. Only enrich on profile generation, not on every read. |
| 360Giving API coverage gaps (not all publishers in API) | Fall back to bulk-file download for missing publishers. Document which orgs have grant data. |
| CRM credential management (API keys per org) | Encrypt at rest. Env vars per org, not hardcoded. MCP server never logs credentials. |
| AT Protocol ecosystem doesn't mature | Lexicons are designed but not built. No sunk cost if we don't deploy. Murmurations continues. |
| Agent over-claims impact | Prompt guardrails + admin confirmation + evidence_type requirement for minting. Hypercert is public and traceable — bad claims are visible. |
| Ethereum gas costs for minting | Optimism mainnet (low gas). Good Ship subsidises during Phase 2. Phase 3: org pays or custodial wallet has funded allowance. |

---

## What this doesn't build

- Access control / tiered permissions (Phase 2.5 — separate spec)
- Strategy matching / cluster detection (Phase 3)
- Funder profiles (Phase 3)
- AT Protocol PDS/relay/App View deployment (Phase 4)
- ActivityPub bridge (not our problem — Murmurations' problem)
- Firecrawl crawler tier (held)
- Org-owned Ethereum wallets (Phase 3)
- CRM webhooks / real-time sync (Phase 3 — polling only in Phase 2)
- Donorfy integration (deferred — new API still being rebuilt)
- CiviCRM / Raisely / Kindful integrations (deferred — Beacon, Lamplight, Salesforce first)