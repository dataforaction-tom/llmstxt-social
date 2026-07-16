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

### 2026-06-16 (guided array fields vs schema item shapes)
**What happened:** Saving an idea failed once the user reached the evidence/connections/collaborators sections: `evidence_base[0] · 'evidence_id' is a required property`, `connections[0] · 'seeking_partners' is not of type 'object'`, `collaborators[0] · 'org_name' is a required property`. The guided card-lists used cardShapes that didn't match the schema's array-*item* shape: evidence cards emitted `{citation, url}` (schema needs `evidence_id`), collaborators emitted `{name}` (needs `org_name`), and connections was a *pills* field emitting strings while the schema wants an array of `{org_name, …}` objects. A wider audit found the same class everywhere: `also_known_as`, `area_codes`, `resource_model.resourcing_gaps` are `string[]` but were modelled as `{value}` object card-lists, and `connections.relationship` is an enum a free-text card can't satisfy.
**Why it was wrong:** The first schema-consistency guard only checked top-level *types* (string/array/object), not array-*item* shapes — so card-list cardShapes and string-vs-object arrays slipped through. The guided field kinds (pills/card-list/`{value}`) were authored without checking each array's `items` schema (required props, string vs object, enums).
**Rule:** For array fields, match the schema's `items`: `string[]` → a string-list control (new `string-list` kind, emits a flat `string[]`); `array<object>` → a card-list whose cardShape includes every *required* item property; never model an object array as pills (emits strings) or a string array as object cards. Enum/boolean sub-fields can't be free-text card inputs — omit them (set via Markdown) until cards support constrained inputs. The guard (`schemaConsistency.test.ts`) now also asserts string-array keys use `string-list` and array<object> keys are card-lists covering required item props.

### 2026-06-16 (new-record save → NOT NULL violation)
**What happened:** Saving a *new* idea failed with a generic "Couldn't save". The cause wasn't validation — it was a DB `IntegrityError`: `null value in column "parent_id" of relation "org_versions" violates not-null constraint`. `put_idea_markdown` creates the new `OrgIdea`, then calls `_snapshot_version(parent_id=idea.id)`. But `idea.id`'s default (`uuid.uuid4`) only fires at flush, so it was still `None` when the version row was built → `parent_id NULL` → rejected. `put_strategy_markdown` and `put_profile_markdown` had the same latent bug for new records.
**Why it was wrong:** A SQLAlchemy column default is applied at INSERT/flush, not at object construction — so reading `obj.id` straight after `db.add(obj)` (before a flush) yields `None`. The codebase already knew this (`_snapshot_version` pre-generates its own UUID for exactly this reason) but the parent records didn't. The unit tests passed because they mock the session, so the real NOT NULL constraint never ran — the bug only appears against Postgres.
**Rule:** When a just-created row's id is needed before commit (e.g. as another row's FK), pre-assign it (`Model(id=uuid.uuid4(), …)`) or `await db.flush()` first — don't read `.id` off an unflushed object. And cover create-paths with a test that asserts the dependent row's FK is non-null (mocked sessions won't surface the DB constraint). Regression: `test_put_idea_md_new_record_snapshot_has_parent_id` + the strategy equivalent.

### 2026-06-16 (guided fields vs schema types)
**What happened:** Saving the guided profile failed with `identity.scale · 'national' is not of type 'object'`. `identity.scale` is a typed *object* in the schema (income band, staff/trustee counts), but the guided spec mapped it to a free-text field with a misleading hint ("local · regional · national · international"). It rendered blank (the value wasn't a string), invited the user to type "national", and overwrote the whole object with a string. A systematic audit (a new schema-consistency test) found the same class across all three record specs: `mission.evidence_summary` and `resource_model.current_funding_mix` (objects mapped to textarea), and `governance.board_size`, `place.geolocation.lat/lon`, `indicative_cost.lower/upper` (numbers/integers mapped to text — a text field emits a string and fails integer validation too).
**Why it was wrong:** The guided spec's field *kinds* (text/textarea/pills/group) were chosen editorially without checking the JSON Schema's *type* at each key. The field system only emitted strings/arrays, so any field pointed at an object/number leaf silently corrupted it on edit. One bad field had shipped; an audit revealed six.
**Rule:** A guided/form field's emitted type must match the schema leaf it writes. Added a `number` field kind (emits an actual number) for integer/number leaves; removed or remapped object-typed fields to a string subfield (e.g. `mission.evidence_summary.beneficiaries_served_text`) or to the markdown surface (scale, funding_mix, geolocation) pending a structured editor. A regression test (`schemaConsistency.test.ts`) now asserts no scalar control maps onto a non-string schema key — when the schema gains a typed field, recheck the guided spec.

### 2026-06-15 (guided editor + chat creator)
**What happened:** Continued local testing surfaced four more bugs in the merged editor work. (1) **Chat creator dead after session start:** `require_org_admin` declares `org_id: str`, but the `get_session`/`post_message`/`finalize` routes had paths like `/create/{session_id}` with no `{org_id}` — so FastAPI bound `org_id` as a *required query* param and every post-session call 422'd. The existing route tests all passed because they call the route functions directly, bypassing FastAPI's dependency/path resolution. (2) **Guided editor couldn't type spaces:** `TextField`/`TextAreaField` were bound straight to a value prop that the guided bridge re-derives by serializing→reparsing markdown on every keystroke and trimming; a space, the instant it became trailing, was stripped before the next char. (3) **Guided preview looked frozen:** it rendered only the markdown body, so edits to frontmatter fields (most of a profile) never appeared. (4) **Guided saves failed silently:** a failed autosave's `validationErrors` were only wired to the markdown surface, so the guided surface gave no reason.
**Why it was wrong:** (1) A dependency parameter only becomes a path param if the route's path template contains it; otherwise FastAPI silently makes it a query param. (1b) Testing a route by calling its function directly verifies the body but not the wiring (path params, DI, auth) — the layer where this class of bug lives. (2) Round-tripping a controlled input through serialize→parse on every keystroke lets normalization (trimming) fight the user's typing. (3/4) A "guided" surface needs its own preview and error affordances; reusing only part of the markdown surface's wiring leaves blind spots.
**Rule:** Any FastAPI route whose dependencies need a path value must include `{that_value}` in the path; add a routing-layer test that asserts `{org_id}` (etc.) is in `route.path`, not just a direct-call unit test. For inputs fed by a lossy round-trip, keep a local buffer in the field component and adopt the prop only when it genuinely changes. When building an alternate editing surface, give it the full set of feedback affordances (preview reflecting *all* edited state, validation errors) — don't assume the shared parent covers it. All four are covered by regression tests (`test_open_org_creator_routes.py`, `TextAreaField.test.tsx`, `GuidedEditor.test.tsx`, `EditorShell.test.tsx`).

### 2026-06-15
**What happened:** Local click-through of the merged #18/#19 editor-polish work surfaced three bugs the merged code shipped with. (1) **Claim redirect raced to /dashboard:** `AuthVerify.tsx` guarded its `<Navigate>` on `status === 'success' || isAuthenticated`, but `AuthContext.verifyToken()` flips `isAuthenticated` true via `refetch()` *before* it returns `claimOrgId` — so the component navigated to the default `redirectTo` (`/dashboard`) before `setRedirectTo(.../profile)` ran, defeating the whole #18 claim-redirect feature even though the backend grant succeeded. (2) **Rate-limit rule over-matched:** `_rule_for` used `path.startswith("/api/open-org/generate")`, which also caught the `/generate/{org_id}/status` polling endpoint — the live-status UI polls it every ~2s, exhausting the 5/hour generate budget in seconds. (3) **Throttling returned 500, not 429:** the middleware `raise HTTPException(429)` inside `BaseHTTPMiddleware.dispatch`, which bypasses FastAPI's exception handlers and surfaces as a 500.
**Why it was wrong:** (1) Deriving a redirect target asynchronously while a separate signal (`isAuthenticated`) can trigger navigation first is a race — the navigation gate must depend only on the state that is set *together with* the target. (2) `startswith` on a path prefix silently captures every sub-route; a rate limit meant for one expensive POST leaked onto a cheap high-frequency GET. (3) `BaseHTTPMiddleware` is not inside FastAPI's exception-handling stack, so `raise HTTPException` there does not become the intended HTTP response.
**Rule:** In React verify/redirect pages, gate `<Navigate>` only on the state set alongside the destination (here `status === 'success'`, which batches with `setRedirectTo`); never also gate on an auth flag that can flip earlier. For rate-limit path rules, match the exact path (`path == "/api/open-org/generate"`) unless every sub-path genuinely shares the budget. From any Starlette/`BaseHTTPMiddleware`, **return** a `JSONResponse(status_code=...)` rather than raising `HTTPException`. All three are now covered by regression tests (`AuthVerify.test.tsx`, `test_rate_limit_rules.py`).

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

### 2026-06-23
**What happened:** Every Open Org generation 404'd because the model id `claude-sonnet-4-20250514` was hardcoded in `llm.py`, `llm_usage.py`, `analyzer.py`, and `assessor.py` — and Sonnet 4 reached end-of-life on 2026-06-15.
**Why it was wrong:** A pinned, dated model id is a time-bomb; nothing failed until the retirement date passed, and unit tests mock the LLM so they never caught it.
**Rule:** Don't hardcode model ids across modules. Route LLM calls through the provider abstraction (`llmstxt_core.llm_providers.build_llm_client` / `Settings.build_llm_client`) and set the model via `LLM_MODEL`. Prefer non-dated aliases (`claude-sonnet-4-6`).

### 2026-06-23
**What happened:** The Murmurations weekly health-check crashed on its first real run (`validation.get("valid")` on a `ValidationResult` dataclass), but tests were green — they mocked `validate_profile` to return a `dict`, a shape the real client never produces.
**Why it was wrong:** A mock that doesn't match the real return type tests a fiction and hides the bug.
**Rule:** Mock with the real type (here `ValidationResult`), not a convenient dict. When mocking a function, check its actual return type first.

### 2026-06-23
**What happened:** Edits to `packages/core` weren't picked up by the running test-stack API even though the source is mounted — `uvicorn --reload` watches the app's cwd (`/app/api`), not the sibling mount `/app/core`. Had to `docker compose ... restart api`.
**Why it was wrong:** Assumed `--reload` covers every mounted dir. It doesn't.
**Rule:** After editing `packages/core`, restart the test-stack `api`/`celery_worker` containers; `--reload` only reflects `packages/api` edits live.

### 2026-06-23
**What happened:** Adding the `openai` dependency means `llmstxt_api.config` now imports it at startup (via the provider factory). The running test containers (built before the dep) would have crashed on boot until `openai` was pip-installed into them.
**Why it was wrong:** A new top-level import in `config` is a hard boot dependency for the whole API.
**Rule:** **Before the next prod deploy, rebuild the image** (`docker compose build`) so `openai` is present — a stale image will fail to start. Same applies to the test stack after pulling these changes.

### 2026-07-05
**What happened:** `llmstxt.social/generate` was 404ing on the retired `claude-sonnet-4-20250514` model even though that was fixed in code on 2026-06-23 (commit `fdd6fb5`, 2026-06-24). Root cause: an orphaned `llmstxt-local-worker-1` / `llmstxt-local-beat-1` container pair (compose service names `worker`/`beat`) from before the services were renamed to `celery_worker`/`celery_beat` — `docker compose up` never removes containers for services no longer declared in the compose file, so the ancient image (predating the model fix, created 2026-06-11) kept running alongside the correctly-named, up-to-date worker/beat. Both consumed the same Redis queue, so `/generate` tasks intermittently landed on the stale worker and 404'd.
**Why it was wrong:** Assumed a code fix + redeploy of `api`/`celery_worker`/`celery_beat` meant the fix was live everywhere; didn't check for leftover containers from a prior service rename still bound to the same broker.
**Rule:** After renaming a compose service, explicitly `docker stop`/`docker rm` the old-named container(s) — don't rely on `docker compose up` to reconcile them away. When a "fixed" bug still reproduces in prod, run `docker ps` and check for duplicate/orphaned containers on the same compose project before re-diagnosing the code.

### 2026-07-05 (assistant session — treated production as a dev sandbox)
**What happened:** Asked to "test the new features in local dev," I ran `docker compose` commands against the `llmstxt-local` project on this Mac Mini — restarting `api`/`celery_worker`/`celery_beat` several times, writing/reverting test data, deleting a Redis rate-limit key, and running the real profile-generate pipeline twice for a real charity — all without first checking whether "local" actually meant local. I was about to propose stopping `worker-1`/`beat-1` entirely (assuming they were stale dev leftovers) when the user asked "are we sure these aren't the real deployed workers?" That single question caught what verification hadn't: `llmstxt-local` is the live production stack (`cloudflared` routes `llmstxt.social` straight to its port 8000; `worker`/`beat` are 2 of the documented 5 production services). A genuinely separate, correctly-isolated sandbox (`llmstxt-test`, `docker-compose.test.yml`, ports 8010/5442/6389) existed the whole time but had its containers sitting `Exited` for 10 days, so it never showed up as an obviously-relevant candidate in `docker ps`.
**Why it was wrong:** I treated a directory/project name (`llmstxt-local`) as evidence of environment, and treated "it's running and responds to health checks" as evidence it was safe to restart and mutate. Neither is evidence of anything — a compose project name is arbitrary, and a container being up says nothing about who else depends on it.
**Rule:** Before running any mutating command (`restart`, `rm`, direct DB/Redis writes, retriggering paid API calls) against a docker compose project on a shared host, verify environment with something that can't lie: check `/etc/cloudflared/config.yml` (or equivalent tunnel/reverse-proxy config) for what hostname routes to what port, check `MISTAKES.md` for a documented "real service list," and check `docker compose ls` for every project's config files before assuming a name implies dev vs. prod. If a dedicated test compose file exists (e.g. `docker-compose.test.yml`), prefer it outright rather than reusing whatever's already running. When a project's own incident log contradicts itself (see the two entries above this one), treat that as a stop sign, not a tie-breaker to guess through.

---

## Patterns that didn't work

<!-- Approaches we tried that turned out to be wrong for this project. Don't try these again. -->

(none yet)

---

## Promoted to CLAUDE.md

<!-- Entries that have been moved into CLAUDE.md as permanent rules. Kept here for reference. -->

(none yet)
