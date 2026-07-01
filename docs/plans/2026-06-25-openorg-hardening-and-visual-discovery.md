# Open Org Hardening + Visual Discovery Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fix all known bugs, make the API tests pass, align Open Org styling with llmstxt.social, build a graph/node visual discovery layer, and close out outstanding spec items.

**Architecture:** Python monorepo (FastAPI + Celery + React/Vite/TypeScript). Open Org is a sub-application served alongside llmstxt.social on the same FastAPI instance. Discovery currently uses Leaflet maps + flat list; we add a force-directed graph view (D3 or cytoscape) showing organisations and ideas as nodes with theme/place relationships as edges.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, Celery, React 18, Vite, TypeScript, Tailwind CSS, Vitest, pytest

---

## Phase 1: Bug Fixes — Make it work reliably

### Task 1: Fix Settings model rejecting valid env vars

**Objective:** The `Settings` Pydantic model doesn't declare `extra="ignore"`, so env vars like `POSTGRES_PASSWORD`, `VITE_STRIPE_PUBLIC_KEY`, `RESEND_FROM_EMAIL` that exist in `.env` for docker-compose/frontend cause `extra_forbidden` validation errors. This blocks all API tests from collecting.

**Files:**
- Modify: `packages/api/src/llmstxt_api/config.py:100-104`
- Test: `packages/api/tests/test_llm_provider_config.py` (should collect and pass after fix)

**Step 1: Write failing test**

Add a test that verifies Settings can be instantiated with extra env vars present:

```python
# packages/api/tests/test_settings_extra_env.py
"""Settings should ignore extra env vars, not crash on them."""
import os
from llmstxt_api.config import Settings

def test_settings_ignores_extra_env_vars(monkeypatch):
    """Docker-compose sets POSTGRES_PASSWORD, VITE_STRIPE_PUBLIC_KEY, etc.
    These aren't Settings fields but must not crash instantiation."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "dummy")
    monkeypatch.setenv("VITE_STRIPE_PUBLIC_KEY", "pk_test_dummy")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "test@example.com")
    # Should not raise
    s = Settings()
    assert s.database_url is not None
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest packages/api/tests/test_settings_extra_env.py -v`
Expected: FAIL — `extra_forbidden` ValidationError

**Step 3: Fix the model config**

In `packages/api/src/llmstxt_api/config.py`, change the `model_config`:

```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

**Step 4: Run ALL API tests**

Run: `.venv/bin/python -m pytest packages/api/tests/ -q`
Expected: All tests pass (203+ tests)

**Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/config.py packages/api/tests/test_settings_extra_env.py
git commit -m "fix(api): ignore extra env vars in Settings model"
```

---

### Task 2: Audit chat creator for type/error handling issues

**Objective:** Review the strategy/idea chat creator for type mismatches, error handling gaps, and edge cases that cause silent failures.

**Files:**
- Inspect: `packages/api/src/llmstxt_api/routes/open_org_creator.py`
- Inspect: `packages/core/src/llmstxt_core/open_org/creator/conversation.py`
- Inspect: `packages/core/src/llmstxt_core/open_org/creator/extractors.py`
- Test: `packages/api/tests/` (existing creator tests)

**Checks to perform:**
1. SSE stream error handling — what happens if the LLM stream throws mid-turn?
2. Session expiry check uses `datetime.utcnow()` — is this consistent with the DB timezone?
3. `finalize_session` — what if `markdown_to_json` produces valid JSON but missing required fields?
4. `_run_turn_sync` generator — does `iterate_in_threadpool` properly propagate exceptions?
5. Document upload — does DOCX extraction handle tables, headers, footers?
6. `get_session` route — path param `session_id` is `uuid.UUID` but route path has `{session_id}` without `{org_id}` prefix in the get route (line 214). Is there a route collision with `create/{kind}`?

**Step 1: Write tests for identified edge cases**

For each issue found, write a failing test first, then fix.

**Step 2: Run tests and fix**

**Step 3: Commit each fix separately**

---

### Task 3: Audit converter for markdown↔JSON edge cases

**Objective:** The converter is the critical bridge — verify it handles edge cases that real organisations will hit.

**Files:**
- Inspect: `packages/core/src/llmstxt_core/open_org/converter.py`
- Test: `packages/core/tests/open_org/test_converter*.py`

**Checks:**
1. Frontmatter with numeric strings that should stay as strings (already fixed per commit a5fe4a4, verify)
2. Nested arrays in frontmatter (e.g., `governance.policies` with `name` + `last_reviewed` objects)
3. Empty markdown body (frontmatter only)
4. Markdown with code blocks containing `##` headings (should not be parsed as sections)
5. Round-trip identity for all three kinds (profile, strategy, idea)
6. HTML comment stripping in various positions
7. Special characters in org names, theme keys

---

### Task 4: Verify all test suites pass end-to-end

**Objective:** Get a clean baseline: core tests, API tests, web tests, tsc, lint.

**Commands:**
```bash
# Core
.venv/bin/python -m pytest packages/core/tests/ -q

# API
.venv/bin/python -m pytest packages/api/tests/ -q

# Web
cd packages/web && npx tsc --noEmit
cd packages/web && npx vitest run
cd packages/web && npm run lint
```

**Commit if any fixes were needed.**

---

## Phase 2: Styling Consistency

### Task 5: Audit design system alignment

**Objective:** The llmstxt.social pages use `bg-gradient-to-b from-primary-50` (blue sky palette) while Open Org uses `surface-paper` (warm cream/ink). The spec says "Good Ship brand. Warm cream, navy headings, sage accents." Need to determine which is the intended design direction and apply consistently.

**Files:**
- Inspect: `packages/web/tailwind.config.js`
- Inspect: `packages/web/src/index.css`
- Inspect: `packages/web/src/components/Layout.tsx`
- Inspect: `packages/web/src/pages/Home.tsx` (llmstxt.social landing)
- Inspect: `packages/web/src/pages/openorg/*.tsx` (Open Org pages)

**Decision needed from Tom:** Should llmstxt.social pages adopt the warm paper/ink editorial style, or should Open Org adopt the blue/white style? The spec says warm cream, navy headings, sage accents — so likely the editorial style is correct for Open Org, and llmstxt.social stays as-is. But the Layout/nav chrome should feel unified.

**Actions:**
1. Ensure the Layout component (nav, footer) uses consistent styling across both products
2. Add sage as an accent colour to the Tailwind config
3. Ensure Open Org pages consistently use the editorial palette (not mixing blue primary buttons with paper backgrounds)
4. Add smooth transitions between llmstxt.social and openorg routes

---

### Task 6: Align Layout navigation for dual-product

**Objective:** The nav should show both products (llmstxt.social + Open Org) and highlight the active one. Currently it may be ambiguous which product you're in.

**Files:**
- Modify: `packages/web/src/components/Layout.tsx`

---

### Task 7: Polish Open Org page styling

**Objective:** Ensure all Open Org pages (Discover, ProfileDetail, EditProfile, EditStrategy, EditIdea, Create, About, Generate, Ideas, NewRecord) use the editorial design system consistently.

**Files:**
- Modify: `packages/web/src/pages/openorg/*.tsx` as needed
- Modify: `packages/web/src/components/openorg/*.tsx` as needed

---

## Phase 3: Visual Discovery — Graph/Node Visualisation

### Task 8: Design the graph visualisation

**Objective:** Build an interactive force-directed graph showing organisations and ideas as nodes, with edges representing shared themes, shared geography, and strategy→idea connections.

**Design:**
- **Nodes:** Organisations (circles, sized by income band), Ideas (diamonds, sized by cost range), Strategies (squares, sized by priority count)
- **Edges:** Shared theme (thin line), shared geography (medium line), strategy→idea (thick directed edge)
- **Interactions:** Click node → side panel with summary + link to detail page. Hover → highlight connected nodes. Filter by theme (toggle themes on/off). Search by name.
- **Layout:** Force-directed with D3 or cytoscape.js. D3 is lighter and more customisable for this aesthetic.
- **Colours:** Theme-based node colours using a categorical palette derived from the 30-theme vocabulary
- **Fallback:** List view toggle for accessibility / small screens

**Tech choice:** D3-force (lighter, more control over aesthetics) or Cytoscape.js (more built-in features). Recommend D3-force with React for the surrounding UI.

**Files:**
- Create: `packages/web/src/components/openorg/GraphDiscovery.tsx`
- Create: `packages/web/src/components/openorg/GraphDiscovery.test.tsx`
- Modify: `packages/web/src/pages/openorg/Discover.tsx` (add graph/list toggle)
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py` (add graph data endpoint)

### Task 9: Add graph data API endpoint

**Objective:** Add an API endpoint that returns nodes and edges in a format ready for D3.

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py`

**Endpoint:**
```
GET /api/open-org/graph?themes=food_access,health&limit=100
Response: {
  nodes: [
    { id: "GB-CHC-1234567", type: "organisation", name: "...", themes: [...], area: "...", income_band: "...", ideas_count: 2, strategy_themes: [...] },
    { id: "idea:GB-CHC-1234567:community-kitchen", type: "idea", name: "...", themes: [...], org_id: "GB-CHC-1234567", cost_range: [80000, 120000] },
    { id: "strategy:GB-CHC-1234567:2025-2028", type: "strategy", name: "...", themes: [...], org_id: "GB-CHC-1234567" }
  ],
  edges: [
    { source: "GB-CHC-1234567", target: "idea:GB-CHC-1234567:community-kitchen", type: "org_idea" },
    { source: "GB-CHC-1234567", target: "GB-CHC-9876543", type: "shared_theme", weight: 3 },
    { source: "GB-CHC-1234567", target: "GB-CHC-9876543", type: "shared_area", weight: 1 }
  ]
}
```

TDD: write tests first for the endpoint.

### Task 10: Build GraphDiscovery React component

**Objective:** Build the D3 force-directed graph component with React.

**Files:**
- Create: `packages/web/src/components/openorg/GraphDiscovery.tsx`
- Create: `packages/web/src/components/openorg/GraphDiscovery.test.tsx`

**Features:**
- Force-directed layout with D3-force
- Node colours by type (org=navy, idea=sage, strategy=warm orange)
- Node sizing by income band / cost range
- Hover highlight connected nodes + dim others
- Click → side panel with org/idea/strategy summary
- Theme filter checkboxes (same as list view)
- Zoom/pan
- List/graph toggle button

### Task 11: Integrate graph into Discover page

**Objective:** Add the graph view as a toggle option on the Discover page, alongside the existing list + map view.

**Files:**
- Modify: `packages/web/src/pages/openorg/Discover.tsx`
- Modify: `packages/web/src/api/openorg.ts` (add graph data fetcher)

---

## Phase 4: Outstanding Spec Items

### Task 12: Claude skills (/org-strategy, /org-idea)

**Objective:** Create the installable Claude skills for consultants and power users, per spec deliverable 2 Mode 1.

**Files:**
- Create: `packages/core/src/llmstxt_core/open_org/claude_skills/org-strategy/SKILL.md`
- Create: `packages/core/src/llmstxt_core/open_org/claude_skills/org-idea/SKILL.md`
- Create: `packages/core/src/llmstxt_core/open_org/claude_skills/org-strategy/theme_vocabulary.json`
- Create: `packages/core/src/llmstxt_core/open_org/claude_skills/org-idea/theme_vocabulary.json`

### Task 13: Clean up stale branches

**Objective:** Delete the 7 local + 2 remote branches that are superseded by merged PRs.

```bash
# Local
git branch -D editor-polish-pr1-bridge editor-polish-pr2-fields editor-polish-pr3-shell editor-polish-pr4-publish openorg-editor-polish-design feat/openorg-area-code-search

# Remote (via gh or git push origin --delete)
git push origin --delete fix/openorg-editor-local-test-pass fix/openorg-providers-and-bug-sweep
```

### Task 14: Update STATE.md, HANDOFF.md, MISTAKES.md

**Objective:** Reflect the current state after all fixes.

### Task 15: Final verification

**Objective:** All tests green, tsc clean, lint clean, docker build succeeds.

```bash
.venv/bin/python -m pytest packages/core/tests/ packages/api/tests/ -q
cd packages/web && npx tsc --noEmit && npx vitest run && npm run lint
docker compose build
```

---

## Outstanding items (user actions — not code)

- Murmurations schema upstream PR (schema drafted at `deploy/murmurations/`)
- Cloudflare Tunnel route for `openorg.good-ship.co.uk`
- Resend domain verification for `hello@openorg.good-ship.co.uk`
- Prod image rebuild + deploy
- Security review M1/M2 items