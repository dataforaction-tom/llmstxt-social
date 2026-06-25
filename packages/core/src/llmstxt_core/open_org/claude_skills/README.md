# Open Org Claude skills

Installable Claude skills for consultants and power users with Claude
access. These skills guide a conversational facilitation that produces
structured markdown templates (with YAML frontmatter) conforming to the
Open Org schemas.

## Skills

| Skill | What it produces | Schema |
|-------|------------------|--------|
| `/org-strategy` | An Open Org strategy document | `org_strategy.schema.json` |
| `/org-idea` | An Open Org idea document | `org_idea.schema.json` |

Both skills output **markdown with YAML frontmatter** — not raw JSON. The
frontmatter carries the structured fields; the body carries the narrative.
The Open Org markdown editor converts markdown ↔ JSON on save, so the
output of these skills can be pasted directly into the editor.

## What's in each skill

Each `SKILL.md` contains:

- **YAML frontmatter** — `name`, `description`, and `triggers` (the slash
  command and natural-language patterns that activate the skill).
- **Conversational flow** — numbered steps, one question per turn, building
  the document progressively.
- **Schema reference** — a summary of the required and optional fields,
  with a pointer to the authoritative JSON schema file.
- **Theme vocabulary** — the 30-theme controlled vocabulary, with a
  pointer to the full `data/themes.json` file for labels and descriptions.
- **Example output** — a complete markdown template showing the expected
  shape.

## File layout

```
claude_skills/
├── README.md                      (this file)
├── org-strategy/
│   └── SKILL.md
└── org-idea/
    └── SKILL.md
```

The skills reference sibling files in the Open Org package:

- `../schemas/org_strategy.schema.json` — the strategy JSON schema
- `../schemas/org_idea.schema.json` — the idea JSON schema
- `../data/themes.json` — the 30-theme controlled vocabulary

## Installing the skills

Claude skills live in a `.claude/skills/` directory. There are two ways to
install these skills:

### Option A — install into a project (shared with a team)

Copy or symlink the skill directories into your project's
`.claude/skills/` folder:

```bash
# from the root of this repo
mkdir -p .claude/skills
cp -r packages/core/src/llmstxt_core/open_org/claude_skills/org-strategy \
      .claude/skills/org-strategy
cp -r packages/core/src/llmstxt_core/open_org/claude_skills/org-idea \
      .claude/skills/org-idea
```

Commit the `.claude/skills/` directory so anyone working in the repo gets
the skills automatically.

### Option B — install into your user-level skills (available everywhere)

Copy the skill directories into `~/.claude/skills/`:

```bash
mkdir -p ~/.claude/skills
cp -r packages/core/src/llmstxt_core/open_org/claude_skills/org-strategy \
      ~/.claude/skills/org-strategy
cp -r packages/core/src/llmstxt_core/open_org/claude_skills/org-idea \
      ~/.claude/skills/org-idea
```

These skills will then be available in every Claude session you start.

### Verifying installation

Start a Claude session in a directory containing (or with access to) the
Open Org package, then invoke:

```
/org-strategy
```

or

```
/org-idea
```

Claude should load the skill and begin the conversational flow. If the
skill doesn't trigger, check that:

- The `SKILL.md` file is at `.claude/skills/org-strategy/SKILL.md` (or
  `org-idea/SKILL.md`).
- The YAML frontmatter is valid (no tabs, consistent indentation).
- The working directory or a parent contains the `packages/core/.../open_org`
  package so the schema and themes file references resolve.

## Using the skills

### `/org-strategy`

Run with a consultant or someone from the organisation present. The flow:

1. **Context** — org, period, existing document?
2. **Priorities** — 3–5 big things, with outcomes, themes, maturity,
   evidence.
3. **Hidden knowledge** — what you're not doing, tensions, learning, how
   failure is handled.
4. **Relationships and ecosystem** — partners, ecosystem position,
   legitimacy.
5. **Resource model** — funding mix, direction, gaps.
6. **Connections** — linked ideas, similar organisations.
7. **Review and output** — valid `org-strategy.json`.

Takes 15–20 minutes with a responsive participant. If an existing strategy
document is provided (PDF, Word, text), the skill ingests it, extracts the
draft structure, and focuses the conversation on the gaps — the hidden
knowledge that strategy documents rarely contain.

### `/org-idea`

Shorter than the strategy flow — 5–10 minutes:

1. **Context** — org, strategy link, development stage.
2. **The idea** — what, where, who, themes.
3. **Grounding** — evidence, cost range, period.
4. **Connections** — other orgs, similar ideas.
5. **Review and output** — valid `org-idea.json`.

An idea is allowed to be small. Don't over-structure it.

## Output

Both skills produce a markdown file. To publish:

1. Paste the markdown into the Open Org editor at
   `openorg.good-ship.co.uk`, or
2. Save the markdown as `{id}.md` in the organisation's hosted directory
   (`/open-org/{org_id}/strategies/` or `/open-org/{org_id}/ideas/`).

The editor's converter runs markdown → JSON, validates against the schema,
and on success publishes the JSON and re-submits to the Murmurations index.

## Profile integration

If the organisation has an existing Open Org profile:

- The skills pull identity, themes, and evidence items from the profile.
- Strategy priorities and idea grounding reference the profile's evidence.
- The skill offers to upload the output to the organisation's hosted
  profile.

## See also

- [Open Org Phase 1 spec](../../../../../../open-org/open-org-phase1-spec.md)
  — full build spec, including the hosted creation tool and editor.
- [`schemas/`](../schemas/) — JSON schemas for profile, strategy, and idea.
- [`data/themes.json`](../data/themes.json) — the 30-theme controlled
  vocabulary.
- [`creator/prompts/`](../creator/prompts/) — the system prompts for the
  hosted creation tool (same conversational flows, served via the Anthropic
  API for organisations without Claude access).