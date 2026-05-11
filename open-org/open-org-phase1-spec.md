# Open Org — Phase 1 Build Spec

This spec is designed to be followed by Claude Code. Read the whole spec before starting. Follow the conventions below for every piece of work.

## Claude Code conventions

### Skills — use these on every task

**`/tdd` — mandatory for all code.** Every feature, route, module, and utility is built test-first using the TDD skill. Red/green/refactor cycle. No exceptions. When building API routes or endpoints, the TDD skill automatically includes security test templates (auth, input validation, data exposure, rate limiting). Use the project's test framework — if none exists yet, set up Vitest for the Node.js/Next.js codebase.

**`/security-review` — run after each deliverable.** After completing each major component (profile generator, creation tool, editor, connector, discovery page), run `/security-review` on the new code. Pay particular attention to: the Anthropic API key handling, magic link auth flow, profile data validation, and the Murmurations index submission endpoint.

**`docs-updater` — update docs with every change.** If the project has a `docs-updater` skill in `.claude/skills/`, use it. Every new module, route, or schema change must be accompanied by documentation updates. README, API docs, and inline JSDoc/TSDoc. If the skill isn't present, maintain docs manually following the same discipline: code and docs ship together, never separately.

**`superpowers` — use if available.** If the project has a `superpowers` skill in `.claude/skills/`, use it for enhanced capabilities. Check for it at the start of each session.

### General approach

- **Read `.claude/skills/` at the start of every session.** Check what skills are available and use them.
- **Check for existing tests before writing new ones.** Don't duplicate. Extend.
- **Check for existing code before writing new modules.** llmstxt.social has existing CC/CH/FTC integration code. Reuse it. Don't rewrite.
- **Commit after each green test.** Small, frequent commits with descriptive messages.
- **Run `/security-review` before marking any deliverable complete.**
- **Update docs before marking any deliverable complete.**
- **Use environment variables for all secrets** (Anthropic API key, Murmurations API endpoints). Never hardcode.
- **Docker-first.** Everything runs in Docker Compose. Test in containers, not bare metal.

---

## Overview

| Deliverable | What it does | Builds on |
|------------|-------------|-----------|
| **1. Profile generator** | Charity number in → Open Org profile JSON out | llmstxt.social |
| **2. Strategy and idea creator** | Guided conversational input → structured schema objects | Claude skills |
| **3. Murmurations connector** | Host profiles, submit to index, keep in sync | llmstxt.social infrastructure |
| **4. Discovery page** | Search and browse Open Org profiles by theme, place, strategy | New — lightweight aggregator |
| **5. Markdown editor** | Organisations edit and maintain their own profiles, strategies, ideas | New — web-based editor |

These five things together create a complete loop: organisations can create profiles, edit and maintain them, publish them to a federated network, and be discovered by funders. No agent yet. No access control yet. No federation protocol yet. Just enough to test whether the data model survives contact with reality.

---

## 1. Profile generator

### What it does

Extends llmstxt.social to output valid Open Org profile JSON alongside the existing llms.txt output. Takes a charity number (or Companies House number, or organisation URL) and generates a minimum viable profile — the five fields needed for the system to work.

### Current state (llmstxt.social)

llmstxt.social already pulls from Charity Commission API, Companies House API, Find That Charity, and organisational websites to generate machine-readable llms.txt profiles. It runs on the Mac Mini, containerised with Docker, and exposed via Cloudflare Tunnel.

### Infrastructure

Phase 1 extends the existing llmstxt.social deployment. Same Mac Mini, same Docker Compose stack, same Cloudflare Tunnel. The new components — Open Org profile generation, hosted creation tool, markdown editor, Murmurations connector, and discovery page — are added to the existing application. No new infrastructure. No migration.

**Extended deployment architecture:**

```
Mac Mini (existing)
├── Docker Compose (extend existing)
│   ├── llmstxt-social (existing app — extend with:)
│   │   ├── llms.txt generation (existing)
│   │   ├── Profile generator (/api/generate → adds Open Org JSON)
│   │   ├── Hosted creation tool (/api/create/*)
│   │   ├── Markdown editor (/edit/*)
│   │   ├── Murmurations connector (background worker)
│   │   ├── Discovery page (/, /organisations, /ideas)
│   │   └── Profile hosting (/open-org/{org_id}/*)
│   │
│   ├── database (extend existing — profiles, sessions, history)
│   │
│   └── cloudflared (existing)
│       └── Add route: openorg.good-ship.co.uk → localhost:3000
│          (or serve under llmstxt.social/open-org/)
│
Cloudflare (existing)
├── DNS: add openorg.good-ship.co.uk (or subdirectory of llmstxt.social)
├── SSL: handled
├── Caching: profile JSONs cached at edge
└── Auth: magic link is app-level, no Cloudflare Access needed
```

**What this means practically:**
- No new servers, no new containers, no new costs
- Profile generator is a new route in the existing app
- Existing CC/CH/FTC integration code is reused directly
- Existing database schema extends with Open Org tables
- `docker compose up` still runs everything
- Cloudflare edge caching means profile JSONs are fast globally
- If the Mac Mini goes down, cached profiles and discovery pages stay available temporarily

### What needs to change

**New output format.** Add an Open Org profile JSON output alongside the existing llms.txt. Same input (charity number), additional output format.

**Minimum viable profile auto-population:**

| Open Org field | Source | Mapping |
|---------------|--------|---------|
| `identity.name` | CC API `charity_name` | Direct |
| `identity.registration.charity_commission_ew` | Input charity number | Direct |
| `identity.registration.companies_house` | CC API `company_number` or CH API | Direct |
| `identity.identifiers.org_id` | Find That Charity | Format as `GB-CHC-{number}` |
| `identity.geography.primary_area` | CC API `area_of_operation[0]` | Needs ONS code lookup |
| `identity.geography.primary_area_code` | ONS code lookup from area name | New — ONS Linked Data API or local lookup table |
| `identity.geography.operating_areas` | CC API `area_of_operation` | Array of area names |
| `identity.scale.annual_income_band` | CC API `latest_income` | Map to band enum |
| `identity.scale.trustee_count` | CC API `trustee_count` | Direct |
| `identity.founded` | CC API `date_of_registration` | Direct |
| `identity.website` | CC API or website scrape | Direct |
| `mission.summary` | CC API `activities` field | LLM rewriting — CC text is often jargon-heavy |
| `mission.objects` | CC API `objects` | Direct |
| `mission.themes` | Derived from objects + activities | LLM extraction — map to Open Org theme vocabulary |
| `governance.board_size` | CC API trustee count | Direct |
| `governance.accounts_filed_to` | CC API `latest_acc_fin_period_end_date` | Direct |
| `identity.identifiers.llms_txt` | llmstxt.social URL | Direct — link to existing output |

**LLM-assisted fields.** Two fields need Anthropic API processing:

1. **`mission.summary`** — Rewrite CC `activities` field into plain language, under 500 characters, no jargon. Organisation can edit later.

2. **`mission.themes`** — Extract from CC `objects` and `activities` text, mapping to the 30-theme controlled vocabulary. Accept themes above 0.7 confidence; flag others for human review.

**ONS geography lookup.** CC API provides area names but not codes. Use a local lookup table mapping common area names to LAD codes (covers 90% of cases), with ONS Linked Data API as fallback.

**Enrichment beyond minimum viable.** Where data is available:
- `identity.contact` from website scrape
- `identity.also_known_as` from CC registered vs working name
- `evidence` stubs from CC annual return data
- `governance.policies` from CC declared policies

### Hosting

Each generated profile hosted at:
```
https://llmstxt.social/open-org/{org_id}/profile.json
```

Where `{org_id}` is org-id.guide format (e.g., `GB-CHC-1234567`).

### Web interface additions

- Toggle: "Also generate Open Org profile" (default on)
- Preview of generated profile with editable fields (mission summary, themes)
- "Approve and publish" button
- Links to hosted profile JSON and Murmurations listing

### API endpoint

```
POST /api/generate
  body: { charity_number: "1234567" }
  response: {
    llms_txt: "https://llmstxt.social/orgs/1234567/llms.txt",
    open_org_profile: "https://llmstxt.social/open-org/GB-CHC-1234567/profile.json",
    murmurations_status: "submitted" | "pending_approval"
  }
```

### TDD approach

Build this test-first using `/tdd`. Key test cases in order:

```
/tdd charity number input returns valid Open Org profile JSON
/tdd profile JSON validates against org-profile.schema.json
/tdd CC API data maps correctly to identity fields
/tdd annual income maps to correct income band enum
/tdd mission summary is rewritten from CC activities (mock Anthropic API)
/tdd themes are extracted from CC objects (mock Anthropic API)
/tdd ONS geography code lookup returns correct LAD code
/tdd profile is hosted at /open-org/{org_id}/profile.json
/tdd invalid charity number returns 400 with clear error
/tdd rate limiting on /api/generate endpoint
```

Security tests are auto-included by the TDD skill for the API route. After all tests are green, run `/security-review` on the profile generator module.

---

## 2. Strategy and idea creator

### What it does

Guided creation of strategies and ideas through conversation, outputting structured markdown templates. Available in three modes: as Claude skills for consultants and power users, as a hosted web tool for any organisation, and as blank templates in the markdown editor.

### Three modes, same output

**Mode 1: Claude skills (`/org-strategy`, `/org-idea`).** For consultants and organisations with Claude access. Rich conversational flow with document ingestion. Best for deep facilitation alongside a real person.

**Mode 2: Hosted creation tool (llmstxt.social).** For any organisation with a browser. A web-based conversational interface on llmstxt.social that uses the Anthropic API behind the scenes. Same questions, same flow, same output — but no Claude subscription required. The organisation authenticates via their magic link, clicks "Create a strategy" or "Add an idea," and gets a guided conversation that produces a pre-filled markdown template loaded into the editor.

**Mode 3: Blank templates in the editor.** For organisations that prefer to write directly. Markdown templates with guided comments explaining what to write in each section.

All three modes produce the same thing: valid markdown with YAML frontmatter, ready for the editor.

### The hosted creation tool

This is the primary path for most organisations. They shouldn't need a Claude subscription or a consultant to describe their own strategy.

**Interface:** A chat-style web UI embedded in llmstxt.social. Left panel: the conversation. Right panel: the markdown template building up in real time as answers come in. The organisation can see their strategy taking shape as they talk.

**Technical implementation:**

```
Browser (chat UI)
  │
  ├── User sends message
  │
  ├── POST /api/create/strategy (or /api/create/idea)
  │   body: {
  │     org_id: "GB-CHC-1234567",
  │     conversation_history: [...],
  │     user_message: "..."
  │   }
  │
  ├── Server calls Anthropic API
  │   ├── System prompt: the creation flow (same as Claude skill)
  │   ├── Context: org profile (if exists), theme vocabulary,
  │   │   schema requirements
  │   ├── Messages: conversation history + new message
  │   └── Model: claude-sonnet-4-20250514
  │
  ├── Response streams back to chat UI
  │
  └── After each exchange, server extracts structured data
      from conversation and updates the live markdown preview
```

**System prompt structure:** The system prompt encodes the same conversational flow as the Claude skill — context gathering, priorities, hidden knowledge, relationships, resource model. It includes the Open Org schema requirements, the theme vocabulary for tag suggestions, and any existing profile data for the organisation. The prompt instructs the model to ask one question at a time, in natural language, and to progressively build a structured output.

**Live markdown preview:** As the conversation progresses, the right panel shows the markdown template filling in. After the user describes their priorities, the priorities section appears. After they discuss tensions, the tensions section appears. This gives immediate feedback — the organisation can see what they're building and course-correct in real time.

**Session management:**
- Conversations are saved server-side, keyed to org_id and session token
- An organisation can leave and return to a partially completed strategy
- Sessions expire after 30 days of inactivity
- Completed strategies are saved as markdown files and loaded into the editor

**Document ingestion:** If the organisation has an existing strategy document, they can upload it (PDF, Word, or text). The API processes it first — extracting structure, priorities, themes — and then the conversation focuses on the gaps: the hidden knowledge that strategy documents rarely contain.

**Cost management:** Each creation session uses the Anthropic API. Estimated token usage per strategy creation: 10-15k input tokens (system prompt + conversation history + profile context), 5-8k output tokens (responses + structured extraction). At current API pricing this is pennies per session. For Phase 1 this can be absorbed. Later phases could rate-limit to prevent abuse or introduce a nominal fee.

### TDD approach for hosted creation tool

Build test-first using `/tdd`:

```
/tdd POST /api/create/strategy accepts org_id and conversation message
/tdd conversation history is maintained across exchanges
/tdd system prompt includes org profile data when available
/tdd system prompt includes theme vocabulary
/tdd response streams back to client
/tdd structured data is extracted from conversation after each exchange
/tdd session is saved and retrievable for returning users
/tdd sessions expire after 30 days of inactivity
/tdd completed strategy outputs valid org-strategy.json
/tdd completed idea outputs valid org-idea.json
/tdd document upload (PDF/Word) is processed before conversation
/tdd magic link auth is required for creation endpoints
/tdd rate limiting prevents API abuse (max 5 sessions per day per org)
/tdd Anthropic API key is never exposed to client
```

Security tests auto-included for all `/api/create/*` routes. Run `/security-review` after completion.

**The end-to-end flow for a new organisation:**

```
1. Arrive at llmstxt.social
2. Enter charity number
3. Profile generated automatically (5 fields, minimum viable)
4. Review and approve profile → published, indexed
5. "Add your strategy" → guided conversation begins
6. 15-20 minute conversation covering priorities, tensions,
   learning, relationships
7. Markdown template generated, loaded into editor
8. Organisation reviews, edits, refines
9. Save → convert → validate → publish → reindex
10. "Add an idea" → shorter conversation
11. Same flow: conversation → template → edit → publish
```

One URL. No accounts beyond a magic link. No Claude subscription. No consultant required. Charity number to full published profile with strategy and ideas in under an hour.

### Claude skills (for consultants and power users)

The same conversational flows also run as Claude skills for consultants working with organisations. Richer interaction — the consultant can steer the conversation, probe deeper, bring their own knowledge of the organisation, and ingest existing documents.

### Skill: `/org-strategy`

**Flow:**

```
1. Context gathering
   ├── "What organisation is this for?" (link to profile if exists)
   ├── "What period does this strategy cover?"
   └── "Is there an existing strategy document?"
        └── If yes: ingest, extract structure, confirm
        └── If no: guided creation

2. Priorities
   ├── "What are the 3-5 big things you're focusing on?"
   ├── For each: outcomes, themes, maturity, evidence
   └── Rank by importance

3. The hidden knowledge
   ├── "What have you decided NOT to do, and why?"
   ├── "What tensions are you holding?"
   ├── "What did you learn that changed your direction?"
   └── "How does this organisation handle things going wrong?"

4. Relationships and ecosystem
   ├── "Who are your key partners? How are those changing?"
   ├── "How do you see your position in the local ecosystem?"
   └── "Where does your legitimacy come from?"

5. Resource model
   ├── "Roughly, what's your funding mix?"
   ├── "Is that changing? Which direction?"
   └── "What can't you currently fund?"

6. Connections
   ├── "Which ideas connect to this strategy?"
   └── "Other organisations with similar direction?"

7. Review and output
   ├── Present draft for review
   ├── User edits and approves
   └── Output: valid org-strategy.json
```

**When an existing document is provided:** Ingest, extract draft structure, then focus conversation on the gaps — the hidden knowledge rarely found in strategy documents.

**Output:** Valid JSON conforming to `org-strategy.schema.json`. Auto-assign themes from vocabulary. Set `status: draft`. Generate first `versions` entry. Set `access_level: summary_public`.

### Skill: `/org-idea`

**Flow:**

```
1. Context
   ├── "What organisation is this for?"
   ├── "Is there a strategy this connects to?"
   └── "How developed is this — seed, or more shaped?"

2. The idea
   ├── "What's the idea?"
   ├── "Where would this happen?"
   ├── "Who would it serve?"
   └── "What themes?" (suggest from vocabulary)

3. Grounding
   ├── "What evidence supports this?"
   ├── "Rough cost range?"
   └── "Over what period?"

4. Connections
   ├── "Other organisations involved?"
   └── "Similar ideas elsewhere?"

5. Review and output
   ├── Present draft
   ├── User edits
   └── Output: valid org-idea.json
```

**Output:** Valid JSON conforming to `org-idea.schema.json`. Set `status` from user's development stage answer.

### Skill installation

Installable via `.claude/skills/` directory. Each skill includes:
- `SKILL.md` with trigger patterns and flow
- Reference to relevant JSON schema
- Theme vocabulary for tag suggestions
- Example outputs

### Profile integration

If organisation has an existing Open Org profile:
- Pull profile for identity, themes, evidence items
- Reference evidence in strategy priorities and idea grounding
- Offer to upload output to hosted profile

---

## 3. Murmurations connector

### What it does

Submits Open Org profiles to the Murmurations index. Handles submission, updates, and validation.

### Schema registration

Before any profiles can be submitted, register with the Murmurations Library:
- Define Open Org field definitions
- Create `open_org_profile-v0.1.0` schema
- Reuse existing Murmurations fields (name, url, geolocation, tags)

### Profile format

Hosted profile JSON must be a valid Murmurations profile. Include `linked_schemas` and required Murmurations fields alongside full Open Org data:

```json
{
  "linked_schemas": ["open_org_profile-v0.1.0"],
  "name": "Riverside Community Trust",
  "primary_url": "https://riverside-trust.org.uk",
  "geolocation": { "lat": 52.6074, "lon": 1.7295 },
  "tags": ["older_people", "loneliness"],
  
  "org_id_guide": "GB-CHC-1234567",
  "strategy_themes": ["food_access", "community_development"],
  "ideas_count": 2,
  
  ...full Open Org profile...
}
```

### Index submission

On publish or update:

```
POST https://index.murmurations.network/v2/nodes
{ "profile_url": "https://llmstxt.social/open-org/GB-CHC-1234567/profile.json" }

Response: { "node_id": "...", "status": "posted" }
```

Store `node_id` for future updates. Re-submit same URL to update.

### Validation

Validate before submitting to live index:

```
POST https://index.murmurations.network/v2/validate
{ "profile_url": "..." }
```

### Geolocation

Murmurations needs lat/lon. CC API doesn't provide coordinates. Use Postcodes.io API to convert postcode (from CC data or website scrape) to lat/lon. Fallback: ONS LAD centroids.

### Implementation

Build as a module within llmstxt.social:
- `murmurations.js` — validation, submission, status tracking
- Runs on profile publish/update
- Stores node_id alongside profile data
- Periodic health check — re-validate stale profiles

### Testing

Use Murmurations test environment first (`test-index.murmurations.network`). Move to production once schema is registered and profiles validate.

### TDD approach

```
/tdd profile JSON includes linked_schemas field for Murmurations
/tdd profile includes required Murmurations fields (name, primary_url, geolocation)
/tdd geolocation is derived from postcode via postcodes.io API
/tdd profile validates against Murmurations validation endpoint (mock in tests)
/tdd index submission returns node_id and posted status (mock in tests)
/tdd node_id is stored alongside profile data
/tdd profile update triggers re-submission to index
/tdd submission errors are logged and retried
/tdd periodic health check re-validates stale profiles
```

Run `/security-review` after completion — particularly around the Murmurations API interaction.

---

## 4. Discovery page

### What it does

A web page querying the Murmurations index for Open Org profiles. Searchable, browsable. The first place a funder can find organisations in the network.

### What it's not

Not the full funder discovery interface. No access requests. No strategy matching. No LLM search. Just: here are the organisations, filter by theme and place, click through.

### Features

**Search by theme.** Checkboxes from the 30-theme vocabulary. Multiple themes narrow results (AND).

**Search by place.** Text input filtered against `identity.geography.primary_area`. Optional map view using Murmurations geolocation data.

**Organisation cards.** Each result shows:
- Name and mission summary (200 chars)
- Primary area
- Theme tags (coloured chips)
- Income band
- Ideas count
- Strategy themes (if present)
- Links to full profile and llms.txt

**Profile detail view.** Rendered view of the full profile — not raw JSON. Strategy priorities, published ideas, evidence summaries. Human-readable, Good Ship branded.

**Idea browser.** Secondary view of published ideas across all organisations. Filterable by theme, place, status, cost range.

### Technical approach

**Data source.** Query Murmurations index API:
```
GET https://index.murmurations.network/v2/nodes?schema=open_org_profile-v0.1.0
```
Returns profile URLs. Fetch each for full data.

**Caching.** Periodic sync (every 6 hours) pulls full list, fetches and caches profile JSONs. Serve from cache.

**Stack.** Part of the same Next.js application running on the Mac Mini. No separate deployment. The discovery page routes (`/`, `/organisations`, `/ideas`) are served by the same app that handles profile generation and editing. Cached profile JSONs are the data — no separate database needed for discovery. Client-side search/filter is fine at tens to hundreds of profiles. Cloudflare edge caching means the discovery pages load fast regardless of Mac Mini location.

**Design.** Good Ship brand. Warm cream, navy headings, sage accents. Same visual language as the landing page.

**URLs:**
```
/                              — Home, search
/organisations                 — Full list, filterable
/organisations/{org_id}        — Profile detail
/ideas                         — Idea browser
/ideas/{org_id}/{idea_id}      — Idea detail
/about                         — What is Open Org
```

**Map view.** Start with embedded Murmurations map filtered to Open Org schema. Replace with custom Leaflet map later if needed.

### TDD approach

```
/tdd index sync fetches profile URLs from Murmurations API
/tdd fetched profiles are cached locally
/tdd cache refreshes on schedule (6 hour interval)
/tdd organisation list renders all cached profiles
/tdd theme filter narrows results correctly (AND logic)
/tdd place filter matches against primary_area
/tdd organisation card displays name, summary, area, themes, income band
/tdd profile detail view renders all published sections
/tdd idea browser lists ideas across all organisations
/tdd idea filter by theme, place, status, cost range works
/tdd empty results show helpful message, not blank page
/tdd malformed profile JSON in cache is skipped gracefully
```

No auth on discovery pages — they're public. Run `/security-review` anyway to check for XSS in rendered profile content and any data leakage.

---

## 5. Markdown editor

### What it does

A web-based markdown editor where organisations create, edit, and maintain their profiles, strategies, and ideas. YAML frontmatter handles structured fields. Markdown body handles narrative. A converter produces valid schema JSON on save. Organisations never touch JSON directly.

### Why markdown

Organisations already write in prose. JSON is for machines. Markdown with frontmatter is the bridge — human-readable, version-controllable, and trivially convertible. The frontmatter carries the structured fields (themes, registration, geography, cost ranges, status). The body carries the narrative (mission summary, strategy priorities, learning reflections, culture). An organisation can edit their profile in something that feels like writing a document, and the system produces valid schema JSON behind the scenes.

### Editing templates

Each object type has a markdown template. The profile generator and Claude skills output these templates (not raw JSON) so organisations can immediately edit what was generated.

**Profile template:**

```markdown
---
# Open Org Profile
schema_version: open-org/v0.1

identity:
  name: "Riverside Community Trust"
  registration:
    charity_commission_ew: "1234567"
    companies_house: "CE012345"
  geography:
    primary_area: "Great Yarmouth"
    primary_area_code: "E07000145"
    operating_areas:
      - Norfolk
      - Suffolk
  scale:
    annual_income_band: "250k-500k"
    staff_count: 8
    volunteer_count: 45
  website: "https://riverside-trust.org.uk"
  founded: "2012-03-15"

mission:
  themes:
    - older_people
    - loneliness
    - community_development
    - food_access
  beneficiaries:
    - Isolated older people
    - Carers

governance:
  board_size: 9
  accounts_filed_to: "2025-03-31"
  policies:
    - name: safeguarding
      last_reviewed: "2025-01-10"
    - name: financial_controls
      last_reviewed: "2024-09-15"
---

## Mission

Supporting isolated older people to build social connections
and maintain independence through community-led programmes
in Great Yarmouth and surrounding areas.

## Theory of change

We believe that loneliness in older people is driven by
the erosion of everyday social infrastructure — the places
and reasons to leave the house. Our programmes rebuild
those touchpoints: community kitchens, walking groups,
befriending, and volunteer-led drop-ins.

## Culture

We're a small team that moves fast and learns publicly.
We involve beneficiaries in programme design from day one.
We're honest about what doesn't work. We trust our
volunteers with real responsibility.

## Values

- Everyone deserves connection
- Listen before you act
- Be honest about failure
```

**Strategy template:**

```markdown
---
# Open Org Strategy
schema_version: open-org-strategy/v0.1
id: "strategy-2025-2028"
status: active
period:
  start: "2025-04-01"
  end: "2028-03-31"
  horizon: "3_5_years"
themes:
  - food_access
  - social_prescribing
  - community_development
  - volunteering
access_level: summary_public
resource_model:
  current_funding_mix:
    grants: 65
    contracts: 20
    earned_income: 10
    donations: 5
  sustainability_direction: diversifying
  resourcing_gaps:
    - Core funding for volunteer coordinator
    - Kitchen equipment and premises costs
---

## Summary

A three-year plan to build a place-based food system in
Great Yarmouth, connecting community kitchens with social
prescribing pathways and volunteer development.

## Priority 1: Build community kitchen infrastructure

*Themes: food_access, community_development*
*Maturity: emerging*

Three community kitchens across Great Yarmouth — Nelson,
Southtown, and Cobholm. Not just food provision but social
infrastructure: a reason to leave the house, a place to
be useful, a pathway into volunteering and connection.

**What success looks like:**
- 3 kitchens operational by 2027
- 200+ regular participants per week
- 30+ active kitchen volunteers

**Dependencies:**
- Premises secured in all three wards
- Partnership with GT Health Partnership for referrals

## Priority 2: Social prescribing pathways

*Themes: social_prescribing, health*
*Maturity: established*

Formalise the referral pathways between GP practices,
community kitchens, and our befriending programme.

**What success looks like:**
- Formal referral agreements with 4 GP practices
- 150+ referrals per year
- 60% conversion from referral to regular attendance

## Not doing

- **Opening a food bank.** We've seen how transactional food
  provision can undermine dignity. Our kitchens are about
  cooking together, not distributing parcels. Others do food
  banking well. We won't duplicate it.

- **Expanding to Norwich.** We've been asked. But depth in one
  place matters more than breadth across two. We'd rather
  be excellent in Yarmouth than adequate in two towns.

## Tensions

- **Growth vs depth.** Three kitchens is ambitious for an
  organisation our size. We're managing this by phasing —
  one per year — and not moving to the next until the
  previous one is self-sustaining with volunteer leadership.

- **Grant dependency vs earned income.** 65% grant-funded
  isn't where we want to be. The kitchens have earned income
  potential (pay-what-you-can meals, catering) but we won't
  pursue it until community trust is established. Revenue
  too early feels extractive.

## Learning

- **The befriending programme taught us about volunteer
  retention.** We lost 40% of volunteers in year one because
  we didn't invest enough in support and supervision. We
  rebuilt with monthly check-ins, peer support groups, and
  a clear progression pathway. Retention is now 80%. This
  shapes how we'll build the kitchen volunteer programme.
  *Source: programme_failure*

- **COVID showed us that food is a connector, not just a need.**
  We ran emergency food deliveries during lockdown and found
  that the conversations on the doorstep mattered more than
  the food. That insight is the foundation of the kitchen
  strategy.
  *Source: pandemic_response*

## Relationships

### Key partnerships

- **GT Health Partnership** — Deepening. They're our route
  into GP practices for social prescribing referrals.
- **Norfolk Food Network** — New. Exploring supply chain
  collaboration for the kitchens.
- **Voluntary Norfolk** — Established. They refer volunteers
  to us and provide DBS processing.

### Ecosystem position

We're the organisation that connects food and social
isolation in Yarmouth. Others do food banking (Salvation
Army, Trussell Trust partner). Others do social activities
for older people (Age UK Norfolk). We sit at the
intersection — using food as the medium for social
connection, not as an end in itself.

### Community mandate

We've been in Yarmouth for 12 years. Our trustees include
three former beneficiaries. Our volunteer team of 45 is
drawn from the communities we serve. When the council
needs to consult on older people's services, they come
to us — not because we're the biggest, but because our
participants trust us and will talk honestly when we
facilitate.
```

**Idea template:**

```markdown
---
# Open Org Idea
schema_version: open-org-idea/v0.1
id: "community-kitchen-network"
status: developing
place:
  description: "Great Yarmouth"
  area_codes:
    - "E07000145"
themes:
  - food_access
  - social_prescribing
  - community_development
beneficiaries:
  - Isolated older people
  - People referred via social prescribing
indicative_cost:
  lower: 80000
  upper: 120000
  currency: GBP
  period: "2 years"
evidence_base:
  - evidence_id: "befriending-eval-2024"
    relevance: "Demonstrates volunteer network building"
  - evidence_id: "food-delivery-covid"
    relevance: "Food as connector, not just provision"
connections:
  - org_name: "Norfolk Food Network"
    relationship: complementary
    mutual: false
collaborators:
  - org_name: "GT Health Partnership"
    role: referral_partner
    confirmed: true
---

## Summary

A network of three community kitchens across Great
Yarmouth, combining food access with social prescribing
pathways and volunteer development. Not food banks —
places to cook together, eat together, and belong.

## The detail

Each kitchen runs three sessions per week. Pay-what-you-can
meals. Volunteer-led cooking with professional supervision.
Referral pathway from GP practices via GT Health
Partnership. Volunteer progression from participant to
helper to kitchen leader.

Phase 1: Nelson ward kitchen (year 1)
Phase 2: Southtown kitchen (year 1-2)
Phase 3: Cobholm kitchen (year 2)
```

### The converter

A JavaScript module that converts between markdown+frontmatter and schema JSON. Bidirectional — so profiles generated from the API or Claude skills can be rendered as editable markdown, and markdown edits produce valid JSON.

**Markdown → JSON:**

1. Parse YAML frontmatter with a library (gray-matter, front-matter)
2. Parse markdown body, splitting on `## ` headings
3. Map headings to schema fields:
   - `## Mission` → `mission.summary`
   - `## Theory of change` → `mission.theory_of_change`
   - `## Culture` → `culture.narrative`
   - `## Priority N: {title}` → `strategy.priorities[n]`
   - `## Not doing` → `strategy.not_doing` (parse `- **bold.**` items)
   - `## Tensions` → `strategy.tensions` (parse `- **bold.**` items)
   - `## Learning` → `strategy.learning.what_changed` (parse items, extract `*Source: x*` tags)
   - `## Summary` → `idea.summary` or `strategy.summary`
4. Merge frontmatter structured data with parsed narrative
5. Validate against JSON schema
6. Output valid JSON

**JSON → Markdown:**

1. Extract structured fields → YAML frontmatter
2. Extract narrative fields → markdown sections with `## ` headings
3. Format arrays (not-doing, tensions, learning) as `- **bold.** description` items
4. Output combined markdown file

**Heading-to-field mapping is configurable per object type.** The converter ships with default mappings for profile, strategy, and idea. Custom mappings can be added for extensions.

### The editor interface

A web-based markdown editor embedded in llmstxt.social. Not building from scratch — use an existing editor component.

**Editor options (pick one):**

| Option | Pros | Cons |
|--------|------|------|
| **Monaco Editor** (VS Code engine) | Powerful, syntax highlighting, familiar | Heavy, overkill for this |
| **CodeMirror 6** | Lightweight, extensible, markdown mode | No WYSIWYG preview |
| **Milkdown** | Markdown WYSIWYG, plugin architecture | Less mature |
| **Tiptap** | Rich text with markdown serialisation | Not native markdown editing |
| **Simple `<textarea>` + preview** | Minimal, fast to build, works everywhere | No syntax help |

**Recommendation: CodeMirror 6 with a live preview pane.** Left side: markdown editing with YAML frontmatter syntax highlighting. Right side: live preview rendered as a styled card (how the profile/strategy/idea will look on the discovery page). Below: validation status (green tick if valid, warnings for missing minimum viable fields).

### Editor flow

```
1. Organisation arrives at their profile page on llmstxt.social
2. Current profile rendered as a readable page (the preview)
3. "Edit" button → opens markdown editor with the profile
   as frontmatter + body
4. User edits in markdown. Preview updates live.
5. On save:
   ├── Converter runs markdown → JSON
   ├── JSON validated against schema
   ├── If valid: save JSON, update hosted profile, re-submit
   │   to Murmurations index
   └── If invalid: show errors inline, don't publish
6. Version history: each save creates a timestamped snapshot.
   User can view previous versions and revert.
```

### Authentication

Organisations need to be able to edit only their own profiles. Lightweight auth:

- **Email-based magic links.** Organisation registers an email when first approving their profile. To edit, they request a magic link sent to that email. Link gives a time-limited session.
- No passwords. No accounts database beyond email + org_id mapping.
- Later phases add proper auth with roles (admin, editor, viewer) from the management interface spec.

### Version history

Every save creates a git-style snapshot. Stored as timestamped markdown files:

```
/open-org/GB-CHC-1234567/
├── profile.json            (current, published)
├── profile.md              (current, editable)
├── history/
│   ├── profile-2026-05-10.md
│   ├── profile-2026-06-15.md
│   └── profile-2026-08-01.md
├── strategies/
│   ├── 2025-2028.json
│   ├── 2025-2028.md
│   └── history/
│       └── 2025-2028-2026-05-10.md
└── ideas/
    ├── community-kitchen-network.json
    ├── community-kitchen-network.md
    └── history/
        └── community-kitchen-network-2026-05-10.md
```

The published JSON is always the converted output of the current markdown. The markdown is the source of truth. The history folder is the audit trail.

### Strategy and idea creation in the editor

The Claude skills (`/org-strategy`, `/org-idea`) output markdown templates, not JSON. The user runs the skill, gets a conversation, and the output is a markdown file that they can paste directly into the editor — or the skill uploads it to their profile.

For organisations that prefer not to use Claude, the editor offers blank templates:
- "New strategy" → opens the strategy markdown template with placeholder prompts
- "New idea" → opens the idea markdown template with placeholder prompts

The prompts in the templates guide the user through the same questions the Claude skill would ask, but as markdown comments:

```markdown
---
# New Open Org Strategy
schema_version: open-org-strategy/v0.1
status: draft
period:
  start:     # When does this strategy start? (YYYY-MM-DD)
  end:       # When does it end?
  horizon:   # 1_year | 2_3_years | 3_5_years | 5_10_years
themes: []   # Pick from: food_access, health, education, etc.
---

## Summary

<!-- What is this organisation trying to become or achieve
     over this period? Write it in plain language, as if
     explaining to someone who knows nothing about you. -->

## Priority 1: [title]

<!-- What's the first big thing you're focusing on?
     What does success look like? How mature is this work? -->

## Not doing

<!-- What have you decided NOT to do? This is often more
     revealing than what you will do. Be honest. -->

## Tensions

<!-- What trade-offs are you holding? Growth vs depth?
     Earned income vs mission? Name them. -->

## Learning

<!-- What failed? What changed? What surprised you?
     How does this organisation handle things going wrong? -->
```

The comments are stripped by the converter — they're guidance for the writer, not data for the schema.

### TDD approach for converter and editor

The converter is the critical module — if it produces invalid JSON the whole system breaks. Build it test-first with comprehensive coverage.

**Converter tests (`/tdd`):**

```
/tdd markdown with YAML frontmatter parses to structured object
/tdd profile markdown converts to valid org-profile.schema.json
/tdd strategy markdown converts to valid org-strategy.schema.json
/tdd idea markdown converts to valid org-idea.schema.json
/tdd markdown comments (<!-- -->) are stripped from output
/tdd ## headings map to correct schema fields per object type
/tdd not-doing items parse from - **bold.** description format
/tdd tensions parse from - **bold.** description format
/tdd learning items extract *Source: type* tags
/tdd JSON converts back to markdown (round-trip)
/tdd round-trip preserves all data (markdown → JSON → markdown → JSON is identical)
/tdd invalid YAML frontmatter returns clear validation error
/tdd missing required fields returns clear validation error listing which fields
```

**Editor tests (`/tdd`):**

```
/tdd editor loads existing profile as markdown
/tdd save triggers converter and validates output
/tdd invalid output shows errors inline without publishing
/tdd valid save updates hosted JSON and triggers Murmurations reindex
/tdd version history creates timestamped snapshot on each save
/tdd magic link auth — valid link grants edit access to correct org only
/tdd magic link auth — expired link returns 401
/tdd magic link auth — link for org A cannot edit org B
/tdd new strategy from blank template has all guided comments
/tdd new idea from blank template has all guided comments
```

Run `/security-review` on the editor module after completion — particularly the magic link auth flow and the converter's handling of malicious YAML/markdown input.

---

## Build sequence

```
Week 1-2:  Profile generator
           ├── Open Org JSON output in llmstxt.social
           ├── CC/CH/FTC → schema field mapping
           ├── LLM mission summary and theme extraction
           ├── ONS geography lookup
           ├── Profile hosting endpoint
           └── Web interface preview/edit/approve

Week 2-3:  Murmurations connector
           ├── Register schema with Murmurations Library
           ├── Build submission module
           ├── Test environment validation
           ├── Geolocation via postcodes.io
           └── Production index submission

Week 3-4:  Markdown editor and converter
           ├── Build markdown ↔ JSON converter module
           ├── Define heading-to-field mappings per object type
           ├── Build editor interface (CodeMirror + preview)
           ├── Add magic link authentication
           ├── Add version history
           ├── Create blank templates with guided prompts
           └── Wire save → convert → validate → publish → reindex

Week 4-5:  Strategy and idea creator
           ├── Build hosted creation tool (chat UI + Anthropic API)
           ├── System prompts for strategy and idea flows
           ├── Live markdown preview during conversation
           ├── Session management and document upload
           ├── /org-strategy and /org-idea Claude skills
           ├── All modes output markdown templates
           ├── Test with 2-3 real organisations
           └── Package Claude skills as installable

Week 5-6:  Discovery page
           ├── Index sync and caching
           ├── Organisation list with search/filter
           ├── Profile detail view
           ├── Idea browser
           ├── Wire into existing app (same Docker container)
           └── Connect to production Murmurations index

Week 6-7:  Real-world testing
           ├── Generate profiles for 5-10 known organisations
           ├── Organisations edit their profiles via markdown editor
           ├── Run /org-strategy with 2-3 willing orgs
           ├── Run /org-idea with 2-3 willing orgs
           ├── Test discovery with real data
           └── Write up what breaks → feeds schema v0.2
```

## Completion checklist — run for every deliverable

Before marking any deliverable complete, Claude Code must:

```
1. All tests green (/tdd — no skipped, no pending)
2. /security-review passed on new code
3. Docs updated (README, API docs, inline docs)
4. Docker build succeeds
5. Docker Compose up runs all services
6. Cloudflare Tunnel routes correctly
7. No hardcoded secrets (check with grep -r "sk-" "api_key" etc.)
8. Environment variables documented in .env.example
9. Git commit with descriptive message
10. If schema files changed: validate all existing test profiles still pass
```

## Risks

| Risk | Mitigation |
|------|-----------|
| Murmurations schema registration takes time | Start conversation early. Build against test environment. Profile generator works independently. |
| CC API data quality | llmstxt.social already handles this. Existing caching applies. |
| Theme extraction accuracy | High-confidence only. Let organisations edit. Track changes to improve. |
| ONS geography mapping gaps | Local lookup table for common areas. Flag unmapped for manual entry. |
| Organisations don't engage | Start with orgs you already work with. Profile generator needs zero effort — just a charity number. |
| Schema changes during build | Version everything. `schema_version` field exists for this. Build migration tooling early. |

## What this doesn't build

Access control and grants (Phase 2). The local agent with MCP integrations (Phase 2). The management interface (Phase 2). Strategy matching and cluster detection (Phase 3). Funder profiles (Phase 3). Federation protocols (Phase 4). Hypercerts integration (Phase 4). `.context` integration (future). MDC collective data layer (future).

All designed for in the schema. Not built yet because they're not needed to answer the question: does the data model work when real organisations use it?
