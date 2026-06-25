# Handoff — Open Org hardening, styling, graph discovery, Claude skills

> Session ended: 2026-06-25
> Branch: `fix/openorg-hardening` (off `master`) — **pushed to origin, PR not yet opened** (gh CLI not authenticated)
> Resumes at: **open the PR**, then **rebuild prod image + deploy**

## TL;DR

A full hardening pass across Open Org: 8 bugs fixed via TDD, design system aligned
with the **actual Good Ship brand** (navy/cream/teal/DM Sans — tokens extracted
from good-ship.co.uk), a new D3 force-directed graph discovery view, and
installable Claude skills for `/org-strategy` and `/org-idea`. All gates green:
**core 314 · API 216 · web 171 · tsc + lint clean**. 14 commits on
`fix/openorg-hardening`, pushed.

## What landed (12 commits, one per fix/feature)

### Bug fixes (8 commits)

1. **`fix(api): ignore extra env vars in Settings model`** — Pydantic-settings v2
   defaults to `extra='forbid'`. The real `.env` has `POSTGRES_PASSWORD`,
   `VITE_STRIPE_PUBLIC_KEY`, `RESEND_FROM_EMAIL` (for docker-compose/frontend) which
   crashed `Settings()` instantiation. This blocked **all** API test collection
   (204 tests unreachable). Fix: `extra="ignore"` in `model_config`. Regression test
   added.

2. **`fix(openorg-creator): emit SSE error event when LLM stream throws mid-turn`** —
   The `event_stream` async generator had no try/except around the LLM stream
   iteration. If the provider threw mid-turn (network error, 5xx, malformed
   response), the exception escaped after 200+headers were sent — the browser's
   EventSource saw an abrupt end with no error event. Fix: wrapped in try/except,
   emit `event: error` SSE frame with the message before returning.

3. **`fix(openorg-creator): extract DOCX tables, headers, and footers`** — Only
   `document.paragraphs` was read. Strategy documents commonly contain tables
   (budgets, timelines) — that content was silently lost. Fix: added table cell
   extraction and header/footer paragraph extraction.

4. **`test(openorg-creator): verify create/get route method disjointness`** —
   Verified that `POST /{org_id}/create/{kind}` and `GET /{org_id}/create/{session_id}`
   don't collide (disjoint HTTP methods). Regression test added.

5. **`fix(openorg): mask fenced code blocks before splitting body sections`** —
   `##` headings inside ```` ``` ```` blocks were incorrectly parsed as schema
   sections, leaking code-block text into JSON fields. Fix: mask fenced code blocks
   (replacing with blank lines) before scanning for headings, then slice content
   from the original body using positions from the masked body.

6. **`fix(openorg): parse and render strategy priorities from body sections`** —
   `## Priority 1: Title` headings were silently dropped during markdown→JSON
   conversion — there was no entry in the body-section parser for priorities. Fix:
   added `parse_priorities`/`render_priorities` with a regex to detect priority
   headings. Wired into both `markdown_to_json` and `json_to_markdown`.

7. **`fix(openorg): parse plain (non-bold) items in not_doing/tensions sections`** —
   `parse_bold_items` only split on `^- **` (bold-prefixed items), silently dropping
   any bullet without a bold prefix. Fix: split on any bullet item (`^- `), classify
   each chunk as bold or plain. Plain items become the `title` with empty body field.

8. **`fix(openorg): coerce unquoted numeric YAML scalars to strings per schema`** —
   YAML parsers read `charity_commission_ew: 1234567` (unquoted) as an integer,
   failing the schema's `type: string` constraint. The previous quoting fix only
   handled the output direction; input was still broken. Fix:
   `_coerce_scalar_types` walks the parsed payload against the JSON Schema and
   coerces int/float/bool leaf values to strings for any path declared `type: string`.

### Styling (2 commits)

9. **`style(openorg): align design system with editorial palette + sage accents`** —
   Initial pass: sage/navy tokens, hostname-aware Layout, 11 hover leaks fixed.
   *(Superseded by commit 14 — kept for history.)*

10. **`style(openorg): align with actual Good Ship brand tokens (navy/cream/teal/DM Sans)`** —
    Replaced the initial editorial palette with the **actual Good Ship brand tokens**
    extracted from good-ship.co.uk CSS custom properties:
    - `paper #FAF7F2` → `cream #F5F0E8`
    - `paper-2` → `cream-dark #EBE4D8`
    - `ink #1A1814` → `navy #1B2A4A`
    - `muted` → `grey-blue #8BA4B8`
    - `sage` → `teal #2D8B7A` / `teal-light #3AA08D`
    - Added `amber #D4993D`, `amber-light`, `coral #C75B3A`, `navy-light`, `paper-white #FEFCF9`
    - `Public Sans` → `DM Sans` (body font — installed @fontsource-variable/dm-sans, removed public-sans)
    - Buttons: teal bg with cream text (not ink bg)
    - `.surface-paper` → `.surface-cream` + added `.surface-navy` for dark sections
    - `.btn-editorial` → `bg-teal text-cream hover:bg-teal-light`
    - GraphDiscovery node colours: orgs=navy, ideas=teal, strategies=amber
    - Added navy-tinted shadows, brand border-radius (8px/16px), transition timing
    - 36 files changed across all Open Org pages and components

### Visual discovery (2 commits)

10. **`feat(openorg): add graph data API endpoint for discovery visualisation`** —
    `GET /api/open-org/graph?themes=food_access,health&limit=100` returns nodes
    (organisations, ideas, strategies) and edges (org_idea, org_strategy,
    shared_theme, shared_area). Supports theme filtering and limit. 8+ TDD tests.

11. **`feat(openorg): add force-directed graph discovery view`** —
    `GraphDiscovery.tsx` (429 lines) using D3-force:
    - Nodes coloured by type: navy (orgs), sage (ideas), orange (strategies)
    - Node sizing by income band / cost range
    - Edges coloured/styled by type (solid, dashed, dotted)
    - Hover: highlight connected nodes + dim unconnected
    - Click: side panel with entity details + link to detail page
    - Zoom/pan via D3 zoom behaviour
    - Theme filter checkboxes
    - Discover page toggle between List+Map and Graph views
    - 5 Vitest tests

### Claude skills (1 commit)

12. **`feat(openorg): add Claude skills for /org-strategy and /org-idea`** —
    Installable SKILL.md files for consultants and power users. Full conversational
    flows matching the spec (7 steps for strategy, 5 for idea), JSON schema
    references, 30-theme vocabulary, heading-to-field mapping, example output
    templates. README.md with installation instructions.

## Deploy notes

- **Rebuild the prod image before deploy** — `config.py` imports `openai` at boot
  (provider abstraction), and the web package now has `d3` as a dependency. A stale
  image will crash.
- New env vars in `.env.example` already documented (`LLM_PROVIDER`, `LLM_MODEL`,
  `OPENROUTER_*`, `OLLAMA_*`).
- `packages/core` edits need a test-stack container restart (uvicorn `--reload`
  doesn't watch `/app/core`).
- D3 adds ~50KB to the web bundle, but GraphDiscovery is lazy-loaded so it only
  loads when the user switches to graph view.

## Flagged, not fixed (low-severity / decisions)

- Cross-product SSO cookie can't span `llmstxt.social` + `good-ship.co.uk` (product
  decision — documented in CLAUDE.md).
- Rate-limit real-client-IP behind Cloudflare/Caddy — verify `trusted_proxies` from
  a real external client.
- Cosmetic: idea/strategy cards show raw slugs as titles; `/discover/ideas`
  `area_code` filter is a no-op.
- Editor polish PR 7 (keyboard + motion polish) — still outstanding from the
  original editor-polish plan.
- Murmurations schema not yet registered upstream.
- `gh` CLI not authenticated on this machine — PR needs to be opened manually.

## Branch cleanup

6 stale local branches deleted:
- `editor-polish-pr1-bridge`, `editor-polish-pr2-fields`, `editor-polish-pr3-shell`,
  `editor-polish-pr4-publish`, `openorg-editor-polish-design`,
  `feat/openorg-area-code-search`

All were superseded by merged PRs (#18–#21). Remote stale branches
(`origin/fix/openorg-editor-local-test-pass`,
`origin/fix/openorg-providers-and-bug-sweep`) may still exist — deletion attempt
returned "remote ref does not exist" which likely means they were already cleaned
up via the GitHub UI.

## How to verify

```bash
# Python (run from repo root)
.venv/bin/python -m pytest packages/core/tests/ -q          # 314 passed
.venv/bin/python -m pytest packages/api/tests/ -q           # 216 passed

# Web (run from packages/web)
npx tsc --noEmit                                             # clean
npx vitest run                                               # 171 passed
npm run lint                                                 # clean
```

## Outstanding user actions

1. **Open PR** → https://github.com/dataforaction-tom/llmstxt-social/pull/new/fix/openorg-hardening
2. **Murmurations schema upstream PR** — schema at `deploy/murmurations/`
3. **Cloudflare Tunnel route** for `openorg.good-ship.co.uk`
4. **Resend domain verification** for `hello@openorg.good-ship.co.uk`
5. **Prod image rebuild + deploy**
6. **Editor polish PR 7** (keyboard + motion polish)