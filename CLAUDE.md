# Project: llmstxt-social + Open Org

A Python monorepo running on a Mac Mini behind Cloudflare Tunnel + Caddy. Two products share infra:

- **llmstxt.social** — generates `llms.txt` profiles for UK charities (existing)
- **openorg.good-ship.co.uk** — Open Org schema profiles, federated via Murmurations (Phase 1, in build)

## Architecture

- `packages/api/` — FastAPI app, Alembic migrations, Celery worker + beat, magic-link auth (Resend)
- `packages/core/` — domain code: enrichers (CC/CH/FTC/360Giving), crawler/extractor/analyzer/generator/validator, plus new `open_org/` submodule (schemas, converter, generator, Murmurations client, themes)
- `packages/web/` — React 18 + Vite + TypeScript SPA. Single build serves both hosts; route tree selected from `window.location.hostname`
- `packages/cli/` — typer CLI
- `deploy/caddy/Caddyfile` — reverse proxy. Cloudflare Tunnel routes to Caddy, Caddy routes to FastAPI on `localhost:8000`

Postgres + Redis run via `docker-compose.yml`. FastAPI serves the Vite build via SPA fallback (so `/` returns the React app on either hostname).

## Commands

- `docker compose up` — full stack
- `pytest tests/` — backend tests (root + per-package)
- `cd packages/web && npm run dev` — frontend dev server (Vite, port 5173)
- `cd packages/web && npm run build && npm run lint`
- `cd packages/api && alembic upgrade head` — run migrations
- `cd packages/api && alembic revision --autogenerate -m "msg"` — new migration

## Standards

- **TDD via the `tdd` skill.** Red/green/refactor for every new module. Security tests auto-included for API routes.
- **`security-review` after each deliverable.** Project-level skill at `.claude/skills/security-review/`.
- **`docs-updater` with every change.** Code and docs ship together.
- **Reuse before rewrite.** `llmstxt_core.enrichers.charity_commission` already returns CC data — don't rebuild it for Open Org.
- **One commit per green test cycle.** Small, frequent.
- **Environment variables for all secrets.** Anthropic key, Murmurations endpoints, Resend key — never hardcode.
- **Docker-first.** Test in containers.

## Verification

Before marking any deliverable complete:
1. All tests green (`pytest`, `npm test` once introduced)
2. `/security-review` passed on new code
3. Docs updated (README, inline docstrings, API docs)
4. `docker compose build` succeeds
5. `docker compose up` runs all services
6. Caddy routes correctly for both hostnames
7. No hardcoded secrets (`grep -r "sk-" packages/`)
8. New env vars documented in `.env.example`
9. If schemas changed: existing test profiles still validate

## Working rules

- Always check existing patterns in the package before creating new ones
- Skills/agents/commands live at project-level `.claude/` — read them at session start
- New JSON schemas live in `packages/core/src/llmstxt_core/open_org/schemas/`
- New API routes follow the pattern in `packages/api/src/llmstxt_api/routes/`
- New Celery tasks follow the pattern in `packages/api/src/llmstxt_api/tasks/`
- Don't refactor existing llmstxt-social code that isn't part of the current task

## State & progress

> Current focus: handed off after Step 4 (editor backend + minimal frontend); Step 5 (profile generator) is next
> Status: 6 of 11 steps complete; 164 backend tests passing; frontend `tsc` clean; nothing committed yet

See `HANDOFF.md` for the session-end wrap-up. `PLAN.md` for the full 11-step build order and locked decisions. `STATE.md` for system state. `MISTAKES.md` for the lessons log.

## Known issues

- Murmurations schema not yet registered upstream (Step 6 — drafting the YAML now; user opens PR)
- Frontend test framework (Vitest+RTL) introduced fresh in Step 4 — first JS tests in repo

## Lessons learned

See `MISTAKES.md`.
