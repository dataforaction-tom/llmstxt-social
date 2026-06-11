# Mistakes & lessons learned

Things that went wrong and what to do instead. After every correction, add an entry. Periodically promote recurring patterns into `CLAUDE.md` and delete from here.

---

## Mistakes log

<!-- Format:
### YYYY-MM-DD
**What happened:** [What Claude did wrong]
**Why it was wrong:** [Why this was a problem in this context]
**Rule:** [What Claude should do instead — be specific and actionable]
-->

### 2026-06-11
**What happened:** Deploying to the production stack, ran `docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.single.yml up -d`. Two failures: (1) the override (which `!reset`s postgres's host port) was listed *before* single.yml, so single.yml re-added `5432:5432` and postgres failed to start against another project's DB on 5432 — prod was down for ~1 minute; (2) bare `up -d` started *every* service in the merged config, including the dev `web` container (port 3000 conflict) and duplicate `celery_worker`/`celery_beat` alongside single.yml's `worker`/`beat` — two beat schedulers would double-fire scheduled tasks.
**Why it was wrong:** Compose merges files left-to-right, so the override must come last to win; and the merged three-file config defines more services than production actually runs.
**Rule:** The production stack is exactly five services — `postgres redis api worker beat` — started with the override LAST: `docker compose -f docker-compose.yml -f docker-compose.single.yml -f docker-compose.override.yml up -d postgres redis api worker beat`. Always name the services; never bare `up -d`. Check `docker compose ls` for the file set a running project was created with before recreating anything.

### 2026-05-10
**What happened:** Wrote a new Alembic migration with `down_revision = 'a1b2c3d4e5f6'`, picking the predecessor by `ls -lat` (most-recently-modified file). All five existing migrations had identical timestamps, so I picked the wrong one — the actual head was `7b64d535033a`. `alembic upgrade head` failed with "Multiple head revisions are present" because the chain branched.
**Why it was wrong:** File mtime is meaningless for migration ordering. Migrations form a graph defined by `revision`/`down_revision` fields; the head is whatever has no descendant pointing at it.
**Rule:** Before authoring a new migration, run `alembic heads` (or trace `down_revision` pointers in the existing files) to find the current head. Never pick from `ls`.

### 2026-05-10
**What happened:** Wrote test files in `packages/api/tests/` that import `llmstxt_api.open_org_models`. All 15 tests failed because importing that module triggers `from llmstxt_api.config import settings`, which instantiates `Settings()` at module load and requires real env vars (DB URL, Anthropic key, Stripe keys, Resend key, secret key, Redis URL).
**Why it was wrong:** I assumed structural model tests were independent of config, forgetting that the SQLAlchemy `Base` import goes through the database module which goes through config.
**Rule:** Any new test file in `packages/api/tests/` that imports an `llmstxt_api.*` module needs dummy env vars set before import. The `tests/conftest.py` does this — keep it as the entry-point for the test environment. New required env vars added to `Settings` must be added to `_TEST_ENV_DEFAULTS` in conftest.

---

## Patterns that didn't work

<!-- Approaches we tried that turned out to be wrong for this project. Don't try these again. -->

(none yet)

---

## Promoted to CLAUDE.md

<!-- Entries that have been moved into CLAUDE.md as permanent rules. Kept here for reference. -->

(none yet)
