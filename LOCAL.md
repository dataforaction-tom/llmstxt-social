# Local click-through guide

End-to-end walkthrough of the Open Org Phase 1 surface, running entirely on
your laptop. No deployed services, no real email deliverability needed.

## Prerequisites

- Docker Desktop running
- Node 20+ (`node --version`)
- `.env` populated with at minimum:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  CHARITY_COMMISSION_API_KEY=...
  ```
  Stripe/Resend keys can be left as the placeholder defaults — the dev-mode
  paths skip them.

## 1. Start the backend

```bash
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head   # one-time per fresh DB
docker compose up api celery_worker
```

The API listens on `http://localhost:8000`. CORS already allows
`http://localhost:5173` (Vite dev) and `http://localhost:3000`.

`ENVIRONMENT=development` is set in `docker-compose.yml`, which enables:
- Magic-link emails print to the **API stdout** instead of going through Resend.
- Open Org claim emails print to the **Celery worker stdout**.
- Auth cookie is host-only (no `Domain=` attribute) so `localhost` works.

Tail the logs in a side terminal:
```bash
docker compose logs -f api celery_worker
```

## 2. Start the frontend

```bash
cd packages/web
npm install        # one-time
npm run dev        # http://localhost:5173
```

## 3. Click-through script

### A. Discovery page (public)

1. Open <http://localhost:5173/openorg/discover>.
2. Empty result set — that's expected. We'll fill it in the next steps.

### B. Generate a profile (unauth → claim)

The generator route is public. Use any UK charity number from
`tests/fixtures/real_world_corpus.yaml` (Trussell Trust = `1110522` is a
good demo — `food_access` should appear in the themes thanks to the
website-crawl augmentation).

```bash
curl -s -X POST http://localhost:8000/api/open-org/generate \
  -H "Content-Type: application/json" \
  -d '{"charity_number": "1110522", "owner_email": "you@example.com"}'
```

Response is an HTTP 202 with a `task_id`. The Celery worker then:
1. Fetches Charity Commission data
2. Crawls the org's website (`collect_website_text`)
3. Calls Anthropic for the mission rewrite + theme extraction
4. Saves `OrgProfile.markdown_source` + `OrgProfile.profile_json`
5. Emits the claim link to stdout — look for `CLAIM LINK for you@example.com (GB-CHC-1110522):` in the worker log

Copy that URL.

### C. Claim the profile

Paste the URL into the browser. The verify route:
- Creates a `User` row
- Sets the auth cookie
- Calls `grant_org_admin(role="owner")` because the magic-link token has
  `org_id` set
- Redirects to `/openorg/edit/GB-CHC-1110522/profile`

### D. Edit the profile

You should now see the CodeMirror editor with the generated markdown on the
left and a live react-markdown preview on the right. Frontmatter is
collapsed behind a `<details>` toggle. Edit something, click **Save profile**
— the PUT goes through the converter + JSON-schema validator. Bad markdown
returns 400 with structured field errors that render below the editor.

### E. Publish the profile

The publish button is currently API-only. Curl it:

```bash
# Cookie file lets curl carry the auth cookie set during claim.
# Easiest: copy the cookie out of your browser's dev tools.

curl -X POST http://localhost:8000/api/open-org/GB-CHC-1110522/publish \
  --cookie "auth_token=<paste-jwt-here>"
```

That sets `published=True` and dispatches the Murmurations submit task
(against the test index by default).

### F. View the public profile

- Full Open Org JSON: <http://localhost:8000/open-org/GB-CHC-1110522/profile.json>
- Murmurations envelope: <http://localhost:8000/open-org/GB-CHC-1110522/murmurations.json>
- Back to discovery: <http://localhost:5173/openorg/discover> — your
  profile should now appear with `source: local`.

### G. Create a strategy via the chat creator

In your browser (still logged in):

<http://localhost:5173/openorg/GB-CHC-1110522/create/strategy>

Either upload an existing strategy doc (PDF/DOCX/TXT) or click **Start
session** with no upload. The chat opens with two panes:
- Left: transcript + send box
- Right: live markdown preview, updated after each assistant turn via the
  `update_current_markdown` tool call

Have a short conversation. When the model says it's ready, click
**Finalise & open editor** — it parses the markdown, creates an
`OrgStrategy` row, and navigates you to the strategy editor for a final
pass.

### H. Idea creator

Same flow, at `/openorg/GB-CHC-1110522/create/idea`.

## What's NOT wired locally

- **Cloudflare Tunnel / subdomain routing** — Step 10. Local clickthrough
  uses `localhost:5173` for everything; the `openorg.*` host-aware redirect
  isn't exercised.
- **Real Resend emails** — dev mode logs the links to stdout instead.
- **Real Murmurations production index** — defaults to `test-index`. Your
  publish action submits there. If the upstream schema PR isn't merged,
  validation will fail at the index — that's fine, the profile is still
  saved + served from the public route.
- **Playwright in the Celery worker** — Chromium isn't installed in the
  worker image yet, so the v0.2.6 fallback won't fire. Mind-class sites
  will degrade to CC-only theme extraction silently.

## Troubleshooting

**"Magic link sent! Check your email" but I don't see a link.** You're in
production mode (`ENVIRONMENT != development`). The compose file should
set it; check `docker compose config | grep ENVIRONMENT`.

**Claim link URL points at the wrong host.** Check `FRONTEND_URL` in the
compose `api` and `celery_worker` services — should be the URL you visit
in the browser (`http://localhost:5173` for Vite, `http://localhost:8000`
if you build and let FastAPI serve).

**Generator task fails silently.** `docker compose logs celery_worker`
— the task wraps errors into the `OrgProfile.generation_error` column.
Visit `/api/open-org/GB-CHC-{number}/profile.md` (authenticated) to see
the row state.

**Discovery page empty even after publish.** The discovery union pulls
from `OrgProfile` where `published=True`. If publish didn't actually flip
the column, the GET will hide the row. `docker compose exec postgres
psql -U postgres -d llmstxt -c "select org_id, published from
org_profiles;"` to confirm.
