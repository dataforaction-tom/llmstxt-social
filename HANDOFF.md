# Handoff — Open Org Phase 1 complete

> Session ended: 2026-05-11
> Branch: master (work uncommitted — ready for review batch + commit)
> Picks up from: end of Step 11 (real-world testing harness)
> Resumes at: commit + first real-world run, then Phase 2 planning

## TL;DR

**Phase 1 is complete.** All 11 steps done; Step 4 stays partial as documented (textarea editor only, no CodeMirror). **352 backend tests pass** (234 core + 118 api), `tsc` clean on the frontend, migration `c2d3e4f5a6b7` (head) up/down/up clean. **Nothing committed yet — this is the review batch.**

## State at handoff

| Step | Status | Notes |
|------|--------|-------|
| 0 — Schemas + themes + validator | ✅ Done | 97 tests |
| 1 — Markdown ↔ JSON converter | ✅ Done | Round-trip identity |
| 2 — DB models + Alembic migration | ✅ Done | `b1c2d3e4f5a6` |
| 3 — CachedAnthropic + llm_usage | ✅ Done | `tools`/`tool_choice` support |
| 4 — Editor + magic-link admin auth | ⚠️ Partial | Backend complete; textarea editor on frontend. CodeMirror/Vitest/live preview/strategy+idea editor pages deferred (documented in PLAN). |
| 5 — Profile generator | ✅ Done | Migration `c2d3e4f5a6b7`. |
| 6 — Murmurations schema YAML | ✅ Drafted | `deploy/murmurations/` — **user opens upstream PR**. |
| 7 — Murmurations connector | ✅ Done | Defaults to test-index; flip via env vars. |
| 8 — Strategy/idea chat creator | ✅ Done | Added `pypdf` + `python-docx`. |
| 9 — Discovery page | ✅ Done | Added `leaflet`, `react-leaflet`, `@types/leaflet`. |
| 10 — Subdomain routing + Caddy | ✅ Done | `AUTH_COOKIE_DOMAIN` env var; Caddyfile updated; `HostRoot` redirects openorg.* root. |
| 11 — Real-world testing harness | ✅ Done | `llmstxt openorg test-corpus` CLI; corpus + report module. **First real run is an operator action.** |

## Action items for the user

Pre-commit:
1. **Review the diff.** Roughly 80 changed/added files across Steps 0–11. The five biggest concentrations are:
   - `packages/core/src/llmstxt_core/open_org/` (schemas, converter, generator, themes, validators, harness, murmurations, ons_geography, creator)
   - `packages/api/src/llmstxt_api/routes/` (open_org_admin, open_org_auth, open_org_creator, open_org_discovery, open_org_generate, open_org_public, open_org_public_murmurations)
   - `packages/api/src/llmstxt_api/tasks/` (open_org_generate, open_org_murmurations)
   - `packages/api/alembic/versions/` (`b1c2d3e4f5a6_open_org_tables.py`, `c2d3e4f5a6b7_open_org_claim_flow.py`)
   - `packages/web/src/api/openorg.ts` + `packages/web/src/pages/openorg/` (EditProfile, Discover) + `App.tsx`
2. **Commit it.** `PLAN.md` has a deliverable-per-step breakdown if a structured commit history is wanted. Otherwise a single commit per step or one Phase-1 mega-commit both work.

Post-commit, before live deploy:
3. **Open the Murmurations upstream PR.** Files in `deploy/murmurations/`. Schema name: `open_org_profile-v0.1.0`.
4. **Verify Resend domain** for `hello@openorg.good-ship.co.uk`. Claim emails ride on it.
5. **Set production env vars**:
   - `AUTH_COOKIE_DOMAIN=.good-ship.co.uk`
   - `MURMURATIONS_INDEX_URL` / `MURMURATIONS_LIBRARY_URL` — flip from test-index after the schema PR merges.
6. **Add the Cloudflare Tunnel route** for `openorg.good-ship.co.uk`:
   ```
   cloudflared tunnel route dns <tunnel-id> openorg.good-ship.co.uk
   ```
   Or use the Zero Trust UI.
7. **Reload Caddy** with the new Caddyfile.

Post-deploy:
8. **Run the harness on real charities.** Edit `tests/fixtures/real_world_corpus.yaml` to add 5-10 charity numbers you know well, then:
   ```
   llmstxt openorg test-corpus
   ```
   Review the generated `tests/reports/real_world_run_<timestamp>.md`. Once happy with a baseline run, copy it to `tests/reports/baseline_v0.1.md` and commit — this becomes the reference for future iterations.

## How to run things

**Backend tests**:
```bash
docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core[dev] -e "packages/api[dev]"
  cd packages/core && python -m pytest tests/ -q
  cd ../api && python -m pytest tests/ -q
'
```
Expected: 234 core + 118 api = **352 passing**.

**Frontend TypeScript check**:
```bash
docker run --rm -v "$(pwd)/packages/web:/work" -w /work node:20-alpine sh -c '
  npm install --silent
  npx tsc --noEmit
'
```
Expected: clean exit.

**Migration sanity check**: unchanged. Head: `c2d3e4f5a6b7`. Step 11 added no new migrations.

**CLI smoke-check**:
```bash
docker run --rm -v "$(pwd):/work" -w /work python:3.11-slim bash -c '
  apt-get update -qq && apt-get install -y -qq build-essential libxml2-dev libxslt1-dev libpq-dev > /dev/null
  pip install --quiet -e packages/core -e packages/cli > /dev/null
  llmstxt openorg test-corpus --help
'
```

## Open follow-ups (post-Phase-1)

These were called out at the time and are surface area for Phase 2 or a focused polish pass — none block ship:

- **Step 4 finish**: CodeMirror 6 editor, live markdown preview, Vitest+RTL setup, strategy/idea editor pages, history restore.
- **Step 5**: rate limiting on `/api/open-org/generate`; route-layer £0.50/org/day cap on generation.
- **Step 7**: live ONS centroid coverage beyond UK nations + major cities; `refresh_from_ons` CLI; Murmurations node deletion when unpublished.
- **Step 8**: daily Celery beat to evict expired `CreatorSession` rows; frontend chat UI.
- **Step 9**: `GET /api/open-org/areas` typeahead; Postgres integration tests for the JSONB filter paths.
- **Step 10**: API tenant gating per host (deliberately left open).
- **Step 11**: diff-vs-baseline mode for the harness; the actual first run (operator action).

## Files written this session (Step 11)

Roughly 5 added / 3 modified.

1. **Core harness**: `packages/core/src/llmstxt_core/open_org/harness.py` (new)
2. **CLI subcommand**: `packages/cli/src/llmstxt_social/openorg.py` (new); wired in `packages/cli/src/llmstxt_social/cli.py`
3. **Empty corpus fixture**: `tests/fixtures/real_world_corpus.yaml` (new)
4. **Reports dir**: `tests/reports/.gitkeep` (new); `.gitignore` excludes `tests/reports/real_world_run_*.md`
5. **Tests** (new):
   - `packages/core/tests/open_org/test_harness.py` (16)
6. **Tracking**: `PLAN.md`, `STATE.md`, this `HANDOFF.md`.

## Notable design decisions made this session

- **CLI sub-app, not a top-level command.** `llmstxt openorg test-corpus` keeps the namespace clean; future Open Org operations land under `llmstxt openorg ...`.
- **Per-charity exception capture, not batch fail.** One bad charity (CC 500, theme extraction yields zero, etc.) becomes a `CharityResult(success=False)` rather than crashing the whole run. Useful when the corpus grows.
- **Empty corpus is a valid input.** `load_corpus` returns `[]`; `run_corpus` returns `[]`; `render_report` writes a "no entries" report. Lets the operator wire the CLI before they have charity numbers picked.
- **Reports are timestamped and git-ignored by default.** The `baseline_v0.1.md` is the long-lived, committed reference; per-run files are workspace artefacts. `tests/reports/.gitkeep` keeps the directory in source so the CLI's default output path works without a pre-flight `mkdir`.
- **Generator is injectable into `run_corpus`.** Same pattern as Step 5's profile generator — production wires `generate_profile_from_charity_number`, tests inject a fake. Keeps the harness tests offline and deterministic.
- **No baseline run committed.** Operator-driven by design. The CLI exits 0 with an empty-corpus warning when invoked against the shipped corpus, so post-clone smoke runs don't surprise anyone.

## How to resume

After commit + first real run, future sessions can:

```
Read CLAUDE.md and PLAN.md. Phase 1 is complete; we're moving into Phase 2 planning.
```

Or for follow-ups:

```
Read PLAN.md "Open follow-ups (post-Phase-1)" and pick the next item.
```
