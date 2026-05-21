# Open Org editor polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the four Open Org user flows (generate / edit profile / add idea / add strategy) lovely to use by adding a dual-surface editor (Guided + existing Markdown), a live generate-progress flow, autosave, a publish-celebration moment, and a microcopy sweep — without backend or converter rewrites.

**Architecture:** A new `EditorShell` wraps the four editor pages and renders either a new `GuidedEditor` (three-column: sidebar nav · focused section · live preview) or the existing `MarkdownEditor`. Both share a single markdown string. A client-side bridge re-serialises only the touched section on each guided edit, so untouched bytes are preserved. Five nullable columns on `OrgProfile` + two new GET routes (`/lookup/{number}`, `/generate/{org_id}/status`) power the live generate progress display.

**Tech Stack:** TypeScript + React 18 + Vite + Vitest/RTL + TanStack Query (frontend); js-yaml (new dep, for the bridge); FastAPI + SQLAlchemy + Alembic + Celery (backend); existing Open Org converter (`packages/core/src/llmstxt_core/open_org/converter.py`).

---

## Source spec

`docs/superpowers/specs/2026-05-19-openorg-editor-polish-design.md` — read this before executing any task. Locked architectural decisions live there.

## PR roadmap

| PR | Theme | Tasks |
|---|---|---|
| 1 | Bridge + section specs | T1.1 – T1.7 |
| 2 | Field components | T2.1 – T2.5 |
| 3 | Guided editor wired into EditProfile | T3.1 – T3.6 |
| 4 | Roll-out + autosave + PublishStrip | T4.1 – T4.7 |
| 5 | Backend status + Generate live flow | T5.1 – T5.8 |
| 6 | WelcomeStrip + microcopy sweep | T6.1 – T6.5 |
| 7 | Keyboard + motion polish | T7.1 – T7.2 |

Each PR lands as its own GitHub PR per the project's "small, frequent" rule. Open a new feature branch per PR off `master` (or off the most-recently-merged branch if PRs are still queueing).

## Working rules (apply to every task)

- **TDD.** Write the failing test first, run it to confirm it fails for the right reason, write the minimal implementation, run it to confirm it passes, commit. Use the `tdd` skill if helpful.
- **No Claude attribution in commits or PRs.** Conventional Commits style; subject ≤ 72 chars.
- **One commit per green test cycle.** Small, frequent.
- **Type-check + lint before commit.** `cd packages/web && npm run build` (this runs `tsc` first) and `npm run lint` for any web change. `pytest` for any backend change.
- **Reuse before rewrite.** Existing components and types in `packages/web/src` and `packages/api/src` are the source of truth — search before creating.
- **Test container scoping.** When asserting on rendered markdown, query inside `article.editorial-preview` to avoid colliding with CodeMirror's editor layer (`MarkdownEditor.test.tsx` is the pattern).
- **No emojis** in source code or commit messages unless the spec or microcopy explicitly calls for one (✓/●/○/↗ are allowed — they're spec-mandated tick states and link affordances).

---

# PR 1 — Bridge + section specs

Goal: a tested `bridge.ts` and three section-spec files. No UI yet. This is the contract the Guided UI is built on top of.

Pre-flight: branch `editor-polish-pr1-bridge` off `master`.

## Task 1.1 — Add js-yaml dependency

**Files:**
- Modify: `packages/web/package.json`

The bridge needs to parse and re-emit YAML frontmatter in the browser. js-yaml is the smallest reliable choice.

- [ ] **Step 1: Add the dependency**

Run from repo root:

```bash
cd packages/web && npm install js-yaml@^4.1.0 && npm install --save-dev @types/js-yaml@^4.0.9
```

- [ ] **Step 2: Verify the install**

Run:

```bash
cd packages/web && npm run build
```

Expected: build succeeds. (No new code yet — this only verifies the dep installs cleanly.)

- [ ] **Step 3: Commit**

```bash
git add packages/web/package.json packages/web/package-lock.json
git commit -m "chore(web): add js-yaml for guided editor bridge"
```

---

## Task 1.2 — `bridge.ts`: YAML key splice

**Files:**
- Create: `packages/web/src/components/openorg/guided/bridge.ts`
- Create: `packages/web/src/components/openorg/guided/bridge.test.ts`

A guided edit changes one or more YAML keys in the frontmatter. The bridge must re-emit only those keys' blocks, leaving untouched keys' raw bytes intact. We do this by scanning the frontmatter line-by-line: a top-level key starts with `^[a-zA-Z_]`, its block runs until the next top-level key or end-of-frontmatter.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/bridge.test.ts
import { describe, expect, it } from 'vitest';
import { spliceFrontmatterKey } from './bridge';

const SOURCE = `---
schema_version: open-org/v0.1
identity:
  name: Riverside Trust
  website: https://riverside.org
mission:
  themes:
    - older_people
---

## Mission

We support older people.
`;

describe('spliceFrontmatterKey', () => {
  it('replaces a top-level key block and leaves other bytes untouched', () => {
    const updated = spliceFrontmatterKey(SOURCE, 'identity', {
      name: 'Riverside Community Trust',
      website: 'https://riverside.org',
    });

    expect(updated).toContain('name: Riverside Community Trust');
    // Untouched keys are byte-identical.
    expect(updated).toContain('schema_version: open-org/v0.1');
    expect(updated).toContain('themes:\n    - older_people');
    // Body is byte-identical.
    expect(updated).toContain('## Mission\n\nWe support older people.\n');
  });

  it('preserves the frontmatter open and close delimiters', () => {
    const updated = spliceFrontmatterKey(SOURCE, 'identity', { name: 'X' });
    expect(updated.startsWith('---\n')).toBe(true);
    // The body following the close delimiter is preserved.
    expect(updated.indexOf('\n---\n\n## Mission')).toBeGreaterThan(0);
  });

  it('adds the key when it is missing', () => {
    const minimal = `---\nschema_version: open-org/v0.1\n---\n\n## Mission\n\nx\n`;
    const updated = spliceFrontmatterKey(minimal, 'identity', { name: 'New' });
    expect(updated).toContain('identity:\n  name: New');
    expect(updated).toContain('schema_version: open-org/v0.1');
  });

  it('throws if the source has no frontmatter', () => {
    expect(() => spliceFrontmatterKey('# heading only\n', 'identity', { name: 'X' })).toThrow(
      /no frontmatter/i,
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- bridge.test`
Expected: FAIL — `Cannot find module './bridge'` or `spliceFrontmatterKey is not exported`.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/bridge.ts
/**
 * Per-section markdown splicer.
 *
 * The Guided editor holds parsed section state and writes back to the
 * markdown source one section at a time. The invariants this module
 * upholds — covered by ``bridge.test.ts``:
 *
 *   1. Any byte of the source markdown OUTSIDE a touched section is
 *      byte-identical before and after the splice.
 *   2. Frontmatter delimiters (``---`` open and close) are preserved.
 *   3. Body sections are split on level-2 headings (``## Heading``);
 *      untouched body sections are byte-identical.
 *
 * The bridge does not perform schema validation — that stays on the
 * backend, where the existing converter validates on save. The bridge's
 * job is purely structural splicing.
 */

import yaml from 'js-yaml';

const FRONTMATTER_OPEN = /^---\r?\n/;
// A top-level YAML key starts at column 0 with a letter or underscore.
const TOP_LEVEL_KEY_RE = /^([a-zA-Z_][a-zA-Z0-9_-]*):/;

interface FrontmatterSplit {
  prefix: string; // ``---\n``
  body: string; // YAML body between the delimiters
  suffix: string; // ``---\n`` + any trailing markdown body
}

function splitFrontmatter(source: string): FrontmatterSplit {
  const openMatch = source.match(FRONTMATTER_OPEN);
  if (!openMatch) {
    throw new Error('no frontmatter found in source');
  }
  const afterOpen = openMatch[0].length;
  // Find the closing ``---`` on its own line.
  const closeIdx = source.indexOf('\n---', afterOpen);
  if (closeIdx === -1) {
    throw new Error('frontmatter has no closing delimiter');
  }
  return {
    prefix: source.slice(0, afterOpen),
    body: source.slice(afterOpen, closeIdx + 1), // include trailing newline
    suffix: source.slice(closeIdx + 1), // starts with ``---``
  };
}

interface KeyBlock {
  key: string;
  startLine: number; // index into ``lines``
  endLine: number; // exclusive
}

function findKeyBlocks(yamlBody: string): KeyBlock[] {
  const lines = yamlBody.split('\n');
  const blocks: KeyBlock[] = [];
  let current: KeyBlock | null = null;

  lines.forEach((line, i) => {
    const match = line.match(TOP_LEVEL_KEY_RE);
    if (match) {
      if (current) {
        current.endLine = i;
        blocks.push(current);
      }
      current = { key: match[1], startLine: i, endLine: lines.length };
    }
  });
  if (current) {
    blocks.push(current);
  }
  return blocks;
}

function renderKeyAsYaml(key: string, value: unknown): string {
  // Render { [key]: value } so js-yaml gives us the ``key: ...`` block we want.
  const dumped = yaml.dump({ [key]: value }, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
  // Ensure trailing newline.
  return dumped.endsWith('\n') ? dumped : dumped + '\n';
}

export function spliceFrontmatterKey(
  source: string,
  key: string,
  value: unknown,
): string {
  const fm = splitFrontmatter(source);
  const lines = fm.body.split('\n');
  const blocks = findKeyBlocks(fm.body);
  const target = blocks.find((b) => b.key === key);

  const rendered = renderKeyAsYaml(key, value);

  let newBody: string;
  if (target) {
    const before = lines.slice(0, target.startLine).join('\n');
    const after = lines.slice(target.endLine).join('\n');
    // Reassemble: before + '\n' (if non-empty) + rendered + after.
    const beforeChunk = before === '' ? '' : before + '\n';
    const afterChunk = after === '' ? '' : after;
    newBody = beforeChunk + rendered + afterChunk;
  } else {
    // Append before the trailing newline that precedes the closing delim.
    const trimmed = fm.body.replace(/\n+$/, '\n');
    newBody = trimmed + rendered;
  }

  return fm.prefix + newBody + fm.suffix;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- bridge.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/bridge.ts packages/web/src/components/openorg/guided/bridge.test.ts
git commit -m "feat(openorg): add spliceFrontmatterKey for guided edits"
```

---

## Task 1.3 — `bridge.ts`: body section splice

**Files:**
- Modify: `packages/web/src/components/openorg/guided/bridge.ts`
- Modify: `packages/web/src/components/openorg/guided/bridge.test.ts`

Body sections (level-2 headings) splice analogously: find the heading, replace the chunk up to the next heading or end of body.

- [ ] **Step 1: Write the failing test**

Append to `bridge.test.ts`:

```typescript
import { spliceBodySection } from './bridge';

describe('spliceBodySection', () => {
  const BODY_SOURCE = `---
schema_version: open-org/v0.1
---

## Mission

Old mission text.

## Values

- Honesty
- Care
`;

  it('replaces a heading section and leaves other body sections intact', () => {
    const updated = spliceBodySection(BODY_SOURCE, 'Mission', 'New mission text.');
    expect(updated).toContain('## Mission\n\nNew mission text.');
    expect(updated).toContain('## Values\n\n- Honesty\n- Care');
    expect(updated).toMatch(/^---\nschema_version/);
  });

  it('appends the section when it is missing', () => {
    const updated = spliceBodySection(BODY_SOURCE, 'Culture', 'Curious and kind.');
    expect(updated).toContain('## Culture\n\nCurious and kind.');
    // Existing sections preserved.
    expect(updated).toContain('## Mission\n\nOld mission text.');
    expect(updated).toContain('## Values\n\n- Honesty');
  });

  it('removes the section when value is empty', () => {
    const updated = spliceBodySection(BODY_SOURCE, 'Mission', '');
    expect(updated).not.toContain('## Mission');
    expect(updated).toContain('## Values');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- bridge.test`
Expected: FAIL — `spliceBodySection is not exported`.

- [ ] **Step 3: Write minimal implementation**

Append to `bridge.ts`:

```typescript
const HEADING_RE = /^## (.+)$/;

interface BodyBlock {
  heading: string;
  startLine: number;
  endLine: number;
}

function findBodyBlocks(bodyText: string): { lines: string[]; blocks: BodyBlock[] } {
  const lines = bodyText.split('\n');
  const blocks: BodyBlock[] = [];
  let current: BodyBlock | null = null;

  lines.forEach((line, i) => {
    const match = line.match(HEADING_RE);
    if (match) {
      if (current) {
        current.endLine = i;
        blocks.push(current);
      }
      current = { heading: match[1].trim(), startLine: i, endLine: lines.length };
    }
  });
  if (current) {
    blocks.push(current);
  }
  return { lines, blocks };
}

function bodyOf(source: string): { preBody: string; body: string } {
  const fm = splitFrontmatter(source);
  // fm.suffix starts with ``---`` (close delim). Everything after the close
  // delim's line is the body.
  const closeNl = fm.suffix.indexOf('\n');
  if (closeNl === -1) {
    return { preBody: fm.prefix + fm.body + fm.suffix, body: '' };
  }
  const preBody = fm.prefix + fm.body + fm.suffix.slice(0, closeNl + 1);
  return { preBody, body: fm.suffix.slice(closeNl + 1) };
}

export function spliceBodySection(source: string, heading: string, value: string): string {
  const { preBody, body } = bodyOf(source);
  const { lines, blocks } = findBodyBlocks(body);
  const target = blocks.find((b) => b.heading === heading);

  const trimmedValue = value.trim();
  const rendered = trimmedValue ? `## ${heading}\n\n${trimmedValue}\n` : '';

  let newBody: string;
  if (target) {
    const before = lines.slice(0, target.startLine).join('\n');
    const after = lines.slice(target.endLine).join('\n');
    const beforeChunk = before === '' ? '' : before + (before.endsWith('\n') ? '' : '\n');
    if (!rendered) {
      // Removing: drop a leading blank line if present.
      const cleanedAfter = after.replace(/^\n+/, '');
      const cleanedBefore = beforeChunk.replace(/\n+$/, '\n');
      newBody = cleanedBefore + cleanedAfter;
    } else {
      // Need a blank line before the new heading if there's content above.
      const sep = beforeChunk && !beforeChunk.endsWith('\n\n') ? '\n' : '';
      const afterSep = after && !after.startsWith('\n') ? '\n' : '';
      newBody = beforeChunk + sep + rendered + afterSep + after;
    }
  } else {
    if (!rendered) {
      newBody = body;
    } else {
      const sep = body.endsWith('\n\n') ? '' : body.endsWith('\n') ? '\n' : '\n\n';
      newBody = body + sep + rendered;
    }
  }

  return preBody + newBody;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- bridge.test`
Expected: PASS for all bridge tests.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/bridge.ts packages/web/src/components/openorg/guided/bridge.test.ts
git commit -m "feat(openorg): add spliceBodySection for guided edits"
```

---

## Task 1.4 — `bridge.ts`: parseSection + serialiseSection

**Files:**
- Modify: `packages/web/src/components/openorg/guided/bridge.ts`
- Modify: `packages/web/src/components/openorg/guided/bridge.test.ts`

The Guided UI binds form fields to a parsed object per section. `parseSection` extracts that object from the source markdown given a section spec (which YAML keys + body headings the section owns). `applySectionEdit` serialises back and splices.

- [ ] **Step 1: Write the failing test**

Append to `bridge.test.ts`:

```typescript
import { parseSection, applySectionEdit, type SectionSpec } from './bridge';

const PROFILE_SPEC: SectionSpec = {
  id: 'identity',
  yamlKeys: ['identity'],
  bodyHeadings: [],
};

const MISSION_SPEC: SectionSpec = {
  id: 'mission',
  yamlKeys: ['mission'],
  bodyHeadings: ['Mission', 'Theory of change'],
};

const FULL_SOURCE = `---
schema_version: open-org/v0.1
identity:
  name: Riverside Trust
  website: https://riverside.org
mission:
  themes:
    - older_people
  beneficiaries:
    - older_people
---

## Mission

We support older people in Norfolk.

## Theory of change

Holistic support reduces isolation.

## Values

- Honesty
`;

describe('parseSection', () => {
  it('returns the YAML keys + body chunks for the section', () => {
    const parsed = parseSection(FULL_SOURCE, PROFILE_SPEC);
    expect(parsed.yaml).toEqual({
      identity: { name: 'Riverside Trust', website: 'https://riverside.org' },
    });
    expect(parsed.body).toEqual({});
  });

  it('returns the body sections owned by the section spec', () => {
    const parsed = parseSection(FULL_SOURCE, MISSION_SPEC);
    expect(parsed.yaml.mission).toEqual({
      themes: ['older_people'],
      beneficiaries: ['older_people'],
    });
    expect(parsed.body.Mission).toMatch(/We support older people/);
    expect(parsed.body['Theory of change']).toMatch(/Holistic support/);
  });
});

describe('applySectionEdit', () => {
  it('round-trips: parse, change one yaml field, apply — only that section changes', () => {
    const parsed = parseSection(FULL_SOURCE, PROFILE_SPEC);
    parsed.yaml.identity = { ...parsed.yaml.identity, name: 'Riverside Community Trust' };
    const updated = applySectionEdit(FULL_SOURCE, PROFILE_SPEC, parsed);

    expect(updated).toContain('name: Riverside Community Trust');
    // Mission section untouched: themes still present and body intact.
    expect(updated).toContain('themes:\n    - older_people');
    expect(updated).toContain('## Mission\n\nWe support older people');
    expect(updated).toContain('## Values\n\n- Honesty');
  });

  it('round-trips a body section edit', () => {
    const parsed = parseSection(FULL_SOURCE, MISSION_SPEC);
    parsed.body.Mission = 'We support older people across East Anglia.';
    const updated = applySectionEdit(FULL_SOURCE, MISSION_SPEC, parsed);

    expect(updated).toContain('## Mission\n\nWe support older people across East Anglia.');
    // Identity untouched.
    expect(updated).toContain('name: Riverside Trust');
    // Other body sections untouched.
    expect(updated).toContain('## Values\n\n- Honesty');
  });

  it('full round-trip with no edits is byte-identical', () => {
    const parsed = parseSection(FULL_SOURCE, MISSION_SPEC);
    const updated = applySectionEdit(FULL_SOURCE, MISSION_SPEC, parsed);
    expect(updated).toBe(FULL_SOURCE);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- bridge.test`
Expected: FAIL — `parseSection`, `applySectionEdit`, and `SectionSpec` not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `bridge.ts`:

```typescript
export interface SectionSpec {
  /** Stable id used for nav + localStorage; matches the section file name. */
  id: string;
  /** Top-level YAML keys this section owns. */
  yamlKeys: string[];
  /** Level-2 body headings this section owns. */
  bodyHeadings: string[];
}

export interface ParsedSection {
  yaml: Record<string, any>;
  body: Record<string, string>;
}

function parseFrontmatterYaml(source: string): Record<string, any> {
  const fm = splitFrontmatter(source);
  const loaded = yaml.load(fm.body) as Record<string, any> | null | undefined;
  return loaded && typeof loaded === 'object' ? loaded : {};
}

export function parseSection(source: string, spec: SectionSpec): ParsedSection {
  const fmDict = parseFrontmatterYaml(source);
  const out: ParsedSection = { yaml: {}, body: {} };
  for (const key of spec.yamlKeys) {
    if (key in fmDict) {
      out.yaml[key] = fmDict[key];
    }
  }
  if (spec.bodyHeadings.length > 0) {
    const { body } = bodyOf(source);
    const { lines, blocks } = findBodyBlocks(body);
    for (const heading of spec.bodyHeadings) {
      const block = blocks.find((b) => b.heading === heading);
      if (block) {
        out.body[heading] = lines.slice(block.startLine + 1, block.endLine).join('\n').trim();
      }
    }
  }
  return out;
}

export function applySectionEdit(
  source: string,
  spec: SectionSpec,
  parsed: ParsedSection,
): string {
  let current = source;
  // Diff against the original parse to decide which keys/headings to splice.
  const original = parseSection(source, spec);

  for (const key of spec.yamlKeys) {
    const before = JSON.stringify(original.yaml[key] ?? null);
    const after = JSON.stringify(parsed.yaml[key] ?? null);
    if (before !== after) {
      if (parsed.yaml[key] === undefined || parsed.yaml[key] === null) {
        // Leave as-is for now; deletion isn't a Phase 1 guided affordance.
        continue;
      }
      current = spliceFrontmatterKey(current, key, parsed.yaml[key]);
    }
  }

  for (const heading of spec.bodyHeadings) {
    const before = (original.body[heading] ?? '').trim();
    const after = (parsed.body[heading] ?? '').trim();
    if (before !== after) {
      current = spliceBodySection(current, heading, after);
    }
  }

  return current;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- bridge.test`
Expected: PASS for all bridge tests.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/bridge.ts packages/web/src/components/openorg/guided/bridge.test.ts
git commit -m "feat(openorg): add parseSection and applySectionEdit"
```

---

## Task 1.5 — Section spec: profile

**Files:**
- Create: `packages/web/src/components/openorg/guided/sections/profile.ts`
- Create: `packages/web/src/components/openorg/guided/sections/profile.test.ts`

Hand-coded section specs per the design spec's profile table.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/sections/profile.test.ts
import { describe, expect, it } from 'vitest';
import { PROFILE_SECTIONS } from './profile';

describe('PROFILE_SECTIONS', () => {
  it('has exactly five sections in display order', () => {
    expect(PROFILE_SECTIONS.map((s) => s.id)).toEqual([
      'identity',
      'mission',
      'governance',
      'culture',
      'values',
    ]);
  });

  it('every section has a friendly name and a non-empty field list', () => {
    for (const section of PROFILE_SECTIONS) {
      expect(section.name).toMatch(/^[A-Z]/);
      expect(section.fields.length).toBeGreaterThan(0);
    }
  });

  it('mission section owns the themes pill field with cap 6', () => {
    const mission = PROFILE_SECTIONS.find((s) => s.id === 'mission')!;
    const themes = mission.fields.find((f) => f.key === 'themes')!;
    expect(themes.kind).toBe('pills');
    expect(themes.selectionCap).toBe(6);
  });

  it('values section owns a top-level array, not a yaml subkey', () => {
    const values = PROFILE_SECTIONS.find((s) => s.id === 'values')!;
    expect(values.yamlKeys).toEqual(['values']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- profile.test`
Expected: FAIL — `Cannot find module './profile'`.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/sections/profile.ts
/**
 * Hand-coded section specs for the profile record kind.
 *
 * Section ordering, names, descriptions, hints, and empty-state prose are
 * editorial — the JSON Schema doesn't carry any of these. Field rendering
 * choices (text vs pill vs card) are also editorial.
 */

import type { SectionSpec } from '../bridge';

export type FieldKind =
  | 'text'
  | 'textarea'
  | 'pills'
  | 'card-list'
  | 'group';

export interface FieldDef {
  /** Path inside the section's yaml owner. E.g. ``identity.name`` becomes
   *  ``yaml.identity.name`` in the ParsedSection. */
  key: string;
  label: string;
  kind: FieldKind;
  hint?: string;
  placeholder?: string;
  /** Pill fields: max selected. Soft cap — UX nudge, not enforced. */
  selectionCap?: number;
  /** Pill fields: name of a vocab loaded at runtime (e.g. ``themes``). */
  vocab?: string;
  /** Group fields: nested children. */
  children?: FieldDef[];
  /** Card list fields: shape of one card. */
  cardShape?: FieldDef[];
}

export interface GuidedSection extends SectionSpec {
  name: string;
  description: string;
  emptyPrompt?: string;
  fields: FieldDef[];
}

export const PROFILE_SECTIONS: GuidedSection[] = [
  {
    id: 'identity',
    name: 'Identity',
    description: 'Who you are — the basics anyone looking you up needs to see first.',
    yamlKeys: ['identity'],
    bodyHeadings: [],
    fields: [
      { key: 'identity.name', label: 'Name', kind: 'text', placeholder: 'The Riverside Trust' },
      {
        key: 'identity.also_known_as',
        label: 'Also known as',
        kind: 'card-list',
        hint: 'Any other names you operate under.',
        cardShape: [{ key: 'value', label: 'Alias', kind: 'text' }],
      },
      { key: 'identity.website', label: 'Website', kind: 'text', placeholder: 'https://...' },
      { key: 'identity.founded', label: 'Founded', kind: 'text', hint: 'Year you started.' },
      {
        key: 'identity.contact',
        label: 'Contact',
        kind: 'group',
        children: [
          { key: 'email', label: 'Email', kind: 'text' },
          { key: 'phone', label: 'Phone', kind: 'text' },
        ],
      },
      {
        key: 'identity.geography',
        label: 'Where you work',
        kind: 'group',
        children: [
          { key: 'description', label: 'Description', kind: 'textarea' },
          { key: 'primary_area', label: 'Primary area code', kind: 'text', hint: 'ONS code, e.g. E07000148.' },
        ],
      },
      { key: 'identity.scale', label: 'Scale', kind: 'text', hint: 'local · regional · national · international' },
    ],
  },
  {
    id: 'mission',
    name: 'Mission',
    description: 'What you exist to do, who you serve, and how you go about it.',
    yamlKeys: ['mission'],
    bodyHeadings: ['Mission', 'Theory of change'],
    fields: [
      { key: 'Mission', label: 'Summary', kind: 'textarea', hint: 'One paragraph; what you do, for whom, where.' },
      {
        key: 'mission.themes',
        label: 'Themes',
        kind: 'pills',
        hint: 'The areas of work that define you. Pick up to six.',
        selectionCap: 6,
        vocab: 'themes',
      },
      {
        key: 'mission.beneficiaries',
        label: 'Beneficiaries',
        kind: 'pills',
        hint: 'Who you serve.',
        vocab: 'beneficiaries',
      },
      { key: 'Theory of change', label: 'Theory of change', kind: 'textarea', hint: 'How your work leads to the outcomes you intend.' },
      {
        key: 'mission.programmes',
        label: 'Programmes',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Name', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
      { key: 'mission.evidence_summary', label: 'Evidence summary', kind: 'textarea' },
    ],
  },
  {
    id: 'governance',
    name: 'Governance',
    description: 'How you are run.',
    yamlKeys: ['governance'],
    bodyHeadings: [],
    fields: [
      { key: 'governance.board_size', label: 'Board size', kind: 'text' },
      { key: 'governance.accounts_filed_to', label: 'Accounts filed to', kind: 'text', hint: 'e.g. Charity Commission for England and Wales.' },
      {
        key: 'governance.policies',
        label: 'Public policies',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Policy name', kind: 'text' },
          { key: 'url', label: 'URL', kind: 'text' },
        ],
      },
    ],
  },
  {
    id: 'culture',
    name: 'Culture',
    description: 'What working with you feels like, in your own words.',
    yamlKeys: ['culture'],
    bodyHeadings: [],
    fields: [
      { key: 'culture.narrative', label: 'Narrative', kind: 'textarea', hint: 'A paragraph or two. Honest, not aspirational.' },
    ],
  },
  {
    id: 'values',
    name: 'Values',
    description: 'What you stand by.',
    emptyPrompt: 'What three or four principles do you keep coming back to? Add one to start.',
    yamlKeys: ['values'],
    bodyHeadings: [],
    fields: [
      {
        key: 'values',
        label: 'Values',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Name', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- profile.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/sections/profile.ts packages/web/src/components/openorg/guided/sections/profile.test.ts
git commit -m "feat(openorg): add profile section spec for guided editor"
```

---

## Task 1.6 — Section spec: strategy

**Files:**
- Create: `packages/web/src/components/openorg/guided/sections/strategy.ts`
- Create: `packages/web/src/components/openorg/guided/sections/strategy.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/sections/strategy.test.ts
import { describe, expect, it } from 'vitest';
import { STRATEGY_SECTIONS } from './strategy';

describe('STRATEGY_SECTIONS', () => {
  it('has nine sections in display order', () => {
    expect(STRATEGY_SECTIONS.map((s) => s.id)).toEqual([
      'overview',
      'period',
      'themes',
      'priorities',
      'not_doing',
      'tensions',
      'learning',
      'relationships',
      'resource_model',
    ]);
  });

  it('overview owns the status pill (single-select)', () => {
    const overview = STRATEGY_SECTIONS.find((s) => s.id === 'overview')!;
    const status = overview.fields.find((f) => f.key.endsWith('status'))!;
    expect(status.kind).toBe('pills');
    expect(status.selectionCap).toBe(1);
  });

  it('not_doing maps to the Not doing body heading', () => {
    const notDoing = STRATEGY_SECTIONS.find((s) => s.id === 'not_doing')!;
    expect(notDoing.bodyHeadings).toContain('Not doing');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- strategy.test`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/sections/strategy.ts
import type { GuidedSection } from './profile';

export const STRATEGY_SECTIONS: GuidedSection[] = [
  {
    id: 'overview',
    name: 'Overview',
    description: 'A name, a one-line summary, and visibility.',
    yamlKeys: ['id', 'status', 'access_level', 'summary'],
    bodyHeadings: ['Summary'],
    fields: [
      { key: 'id', label: 'Slug', kind: 'text', hint: 'URL-stable id, lowercase-and-dashes.' },
      {
        key: 'status',
        label: 'Status',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'strategy_status',
      },
      {
        key: 'access_level',
        label: 'Visibility',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'access_level',
      },
      { key: 'Summary', label: 'Summary', kind: 'textarea', hint: 'One paragraph; the strategy in plain English.' },
    ],
  },
  {
    id: 'period',
    name: 'Period',
    description: 'When this strategy runs.',
    yamlKeys: ['period'],
    bodyHeadings: [],
    fields: [
      { key: 'period.start', label: 'Start', kind: 'text', placeholder: '2026-01' },
      { key: 'period.end', label: 'End', kind: 'text', placeholder: '2028-12' },
      {
        key: 'period.horizon',
        label: 'Horizon',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'horizon',
      },
    ],
  },
  {
    id: 'themes',
    name: 'Themes',
    description: 'What this strategy is about.',
    yamlKeys: ['themes'],
    bodyHeadings: [],
    fields: [
      {
        key: 'themes',
        label: 'Themes',
        kind: 'pills',
        selectionCap: 6,
        vocab: 'themes',
      },
    ],
  },
  {
    id: 'priorities',
    name: 'Priorities',
    description: 'The concrete things you intend to do.',
    emptyPrompt: 'What two to five priorities define this strategy? Add one to start.',
    yamlKeys: ['priorities'],
    bodyHeadings: [],
    fields: [
      {
        key: 'priorities',
        label: 'Priorities',
        kind: 'card-list',
        cardShape: [
          { key: 'title', label: 'Title', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
  {
    id: 'not_doing',
    name: 'Not doing',
    description: 'What you are deliberately not doing.',
    yamlKeys: [],
    bodyHeadings: ['Not doing'],
    fields: [
      { key: 'Not doing', label: 'Not doing', kind: 'textarea', hint: 'Items follow the - **Title** rationale shape.' },
    ],
  },
  {
    id: 'tensions',
    name: 'Tensions',
    description: 'Trade-offs you live with.',
    yamlKeys: [],
    bodyHeadings: ['Tensions'],
    fields: [
      { key: 'Tensions', label: 'Tensions', kind: 'textarea', hint: 'Items follow the - **Title** narrative shape.' },
    ],
  },
  {
    id: 'learning',
    name: 'Learning',
    description: 'What has changed your thinking.',
    yamlKeys: [],
    bodyHeadings: ['Learning'],
    fields: [
      { key: 'Learning', label: 'Learning', kind: 'textarea', hint: 'Bulleted lessons. *Source: …* tags optional.' },
    ],
  },
  {
    id: 'relationships',
    name: 'Relationships',
    description: 'Who you work with and where you sit.',
    yamlKeys: ['relationships'],
    bodyHeadings: [],
    fields: [
      {
        key: 'relationships.partnerships',
        label: 'Partnerships',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Partner', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
      { key: 'relationships.ecosystem_position', label: 'Ecosystem position', kind: 'textarea' },
      { key: 'relationships.community_mandate', label: 'Community mandate', kind: 'textarea' },
    ],
  },
  {
    id: 'resource_model',
    name: 'Resource model',
    description: 'How you fund the work.',
    yamlKeys: ['resource_model'],
    bodyHeadings: [],
    fields: [
      { key: 'resource_model.current_funding_mix', label: 'Current funding mix', kind: 'textarea' },
      { key: 'resource_model.sustainability_direction', label: 'Sustainability direction', kind: 'textarea' },
      {
        key: 'resource_model.resourcing_gaps',
        label: 'Resourcing gaps',
        kind: 'card-list',
        cardShape: [
          { key: 'title', label: 'Gap', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- strategy.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/sections/strategy.ts packages/web/src/components/openorg/guided/sections/strategy.test.ts
git commit -m "feat(openorg): add strategy section spec for guided editor"
```

---

## Task 1.7 — Section spec: idea

**Files:**
- Create: `packages/web/src/components/openorg/guided/sections/idea.ts`
- Create: `packages/web/src/components/openorg/guided/sections/idea.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/sections/idea.test.ts
import { describe, expect, it } from 'vitest';
import { IDEA_SECTIONS } from './idea';

describe('IDEA_SECTIONS', () => {
  it('has seven sections in display order', () => {
    expect(IDEA_SECTIONS.map((s) => s.id)).toEqual([
      'summary',
      'detail',
      'place',
      'themes_beneficiaries',
      'indicative_cost',
      'evidence_base',
      'connections',
    ]);
  });

  it('place is a group', () => {
    const place = IDEA_SECTIONS.find((s) => s.id === 'place')!;
    expect(place.fields[0].kind).toBe('group');
  });

  it('evidence_base is a card list', () => {
    const ev = IDEA_SECTIONS.find((s) => s.id === 'evidence_base')!;
    expect(ev.fields[0].kind).toBe('card-list');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- idea.test`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/sections/idea.ts
import type { GuidedSection } from './profile';

export const IDEA_SECTIONS: GuidedSection[] = [
  {
    id: 'summary',
    name: 'Summary',
    description: 'A name, status, and short summary.',
    yamlKeys: ['id', 'status'],
    bodyHeadings: ['Summary'],
    fields: [
      { key: 'id', label: 'Slug', kind: 'text', hint: 'URL-stable id, lowercase-and-dashes.' },
      {
        key: 'status',
        label: 'Status',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'idea_status',
      },
      { key: 'Summary', label: 'Summary', kind: 'textarea', hint: 'One paragraph; the idea in plain English.' },
    ],
  },
  {
    id: 'detail',
    name: 'Detail',
    description: 'The longer explanation.',
    yamlKeys: [],
    bodyHeadings: ['The detail'],
    fields: [
      { key: 'The detail', label: 'Detail', kind: 'textarea' },
    ],
  },
  {
    id: 'place',
    name: 'Place',
    description: 'Where this would happen.',
    yamlKeys: ['place'],
    bodyHeadings: [],
    fields: [
      {
        key: 'place',
        label: 'Place',
        kind: 'group',
        children: [
          { key: 'description', label: 'Description', kind: 'textarea' },
          { key: 'area_codes', label: 'Area codes', kind: 'card-list', cardShape: [{ key: 'value', label: 'Code', kind: 'text' }] },
          {
            key: 'geolocation',
            label: 'Geolocation',
            kind: 'group',
            children: [
              { key: 'lat', label: 'Lat', kind: 'text' },
              { key: 'lon', label: 'Lon', kind: 'text' },
            ],
          },
        ],
      },
    ],
  },
  {
    id: 'themes_beneficiaries',
    name: 'Themes & beneficiaries',
    description: 'What it is about and who it is for.',
    yamlKeys: ['themes', 'beneficiaries'],
    bodyHeadings: [],
    fields: [
      { key: 'themes', label: 'Themes', kind: 'pills', selectionCap: 6, vocab: 'themes' },
      { key: 'beneficiaries', label: 'Beneficiaries', kind: 'pills', vocab: 'beneficiaries' },
    ],
  },
  {
    id: 'indicative_cost',
    name: 'Indicative cost',
    description: 'Rough order of magnitude — refine later.',
    yamlKeys: ['indicative_cost'],
    bodyHeadings: [],
    fields: [
      {
        key: 'indicative_cost',
        label: 'Cost',
        kind: 'group',
        children: [
          { key: 'lower', label: 'Lower', kind: 'text' },
          { key: 'upper', label: 'Upper', kind: 'text' },
          { key: 'currency', label: 'Currency', kind: 'text', placeholder: 'GBP' },
          { key: 'period', label: 'Period', kind: 'text', placeholder: 'one-off / per-year' },
        ],
      },
    ],
  },
  {
    id: 'evidence_base',
    name: 'Evidence base',
    description: 'What this is built on.',
    emptyPrompt: 'A study, a report, your own data — add one to start.',
    yamlKeys: ['evidence_base'],
    bodyHeadings: [],
    fields: [
      {
        key: 'evidence_base',
        label: 'Evidence',
        kind: 'card-list',
        cardShape: [
          { key: 'citation', label: 'Citation', kind: 'textarea' },
          { key: 'url', label: 'URL', kind: 'text' },
        ],
      },
    ],
  },
  {
    id: 'connections',
    name: 'Connections',
    description: 'Who else cares, who might help.',
    yamlKeys: ['connections', 'collaborators', 'linked_strategy_id'],
    bodyHeadings: [],
    fields: [
      { key: 'connections', label: 'Connections', kind: 'pills', vocab: 'connections' },
      {
        key: 'collaborators',
        label: 'Collaborators',
        kind: 'card-list',
        cardShape: [{ key: 'name', label: 'Name', kind: 'text' }],
      },
      { key: 'linked_strategy_id', label: 'Linked strategy', kind: 'text', hint: 'Slug of a strategy on the same org.' },
    ],
  },
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- idea.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/sections/idea.ts packages/web/src/components/openorg/guided/sections/idea.test.ts
git commit -m "feat(openorg): add idea section spec for guided editor"
```

- [ ] **Step 6: PR 1 lint + build gate**

Run: `cd packages/web && npm run build && npm run lint && npm test`
Expected: all green. Open PR 1 (`editor-polish-pr1-bridge`) to `master`.

---

# PR 2 — Field components

Goal: five colocated, tested field components. No editor wiring yet — components are tested in isolation with props.

Pre-flight: branch `editor-polish-pr2-fields` off the PR1 branch (or off `master` once PR1 is merged).

## Task 2.1 — TextField

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/TextField.tsx`
- Create: `packages/web/src/components/openorg/guided/fields/TextField.test.tsx`

A single-line text input with label, optional hint, and an optional source chip ("from Commission filing", "from website", etc.). The chip disappears the moment the user edits the value.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/fields/TextField.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TextField from './TextField';

describe('TextField', () => {
  it('renders the label, placeholder, and current value', () => {
    render(
      <TextField label="Name" value="Riverside Trust" placeholder="The Trussell Trust" onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText(/name/i)).toHaveValue('Riverside Trust');
    expect(screen.getByPlaceholderText(/trussell/i)).toBeInTheDocument();
  });

  it('renders the hint when provided', () => {
    render(<TextField label="Founded" value="" hint="Year you started." onChange={vi.fn()} />);
    expect(screen.getByText('Year you started.')).toBeInTheDocument();
  });

  it('shows the source chip and hides it on first edit', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TextField label="Name" value="Trussell Trust" source="cc" onChange={onChange} />,
    );
    expect(screen.getByText(/from commission filing/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'New name' } });
    expect(onChange).toHaveBeenCalledWith('New name');

    rerender(<TextField label="Name" value="New name" source="cc" onChange={onChange} userEdited />);
    expect(screen.queryByText(/from commission filing/i)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- TextField`
Expected: FAIL — `Cannot find module './TextField'`.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/fields/TextField.tsx
import { useId } from 'react';

export type FieldSource = 'cc' | 'website' | 'inferred';

const SOURCE_LABELS: Record<FieldSource, string> = {
  cc: 'from Commission filing',
  website: 'from website',
  inferred: 'inferred',
};

interface TextFieldProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  hint?: string;
  placeholder?: string;
  source?: FieldSource;
  /** When true, the source chip is hidden (user has overwritten the value). */
  userEdited?: boolean;
}

export default function TextField({
  label,
  value,
  onChange,
  hint,
  placeholder,
  source,
  userEdited,
}: TextFieldProps) {
  const id = useId();
  const showChip = source && !userEdited;
  return (
    <label htmlFor={id} className="flex flex-col text-sm">
      <span className="kicker mb-2 flex items-center gap-2">
        {label}
        {showChip && (
          <span className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">
            {SOURCE_LABELS[source]}
          </span>
        )}
      </span>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="border border-rule bg-paper px-3 py-2 text-base text-ink focus:border-ink focus:outline-none"
      />
      {hint && <span className="mt-1 text-xs italic text-muted">{hint}</span>}
    </label>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- TextField`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/TextField.tsx packages/web/src/components/openorg/guided/fields/TextField.test.tsx
git commit -m "feat(openorg): add guided TextField component"
```

---

## Task 2.2 — TextAreaField

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/TextAreaField.tsx`
- Create: `packages/web/src/components/openorg/guided/fields/TextAreaField.test.tsx`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/fields/TextAreaField.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TextAreaField from './TextAreaField';

describe('TextAreaField', () => {
  it('renders label, value, and hint', () => {
    render(
      <TextAreaField label="Summary" value="We do good." hint="One paragraph." onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText(/summary/i)).toHaveValue('We do good.');
    expect(screen.getByText('One paragraph.')).toBeInTheDocument();
  });

  it('emits change on input', () => {
    const onChange = vi.fn();
    render(<TextAreaField label="Summary" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/summary/i), { target: { value: 'New' } });
    expect(onChange).toHaveBeenCalledWith('New');
  });

  it('hides the source chip once userEdited', () => {
    render(
      <TextAreaField label="Summary" value="x" source="website" userEdited onChange={vi.fn()} />,
    );
    expect(screen.queryByText(/from website/i)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- TextAreaField`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/fields/TextAreaField.tsx
import { useId } from 'react';
import type { FieldSource } from './TextField';

const SOURCE_LABELS: Record<FieldSource, string> = {
  cc: 'from Commission filing',
  website: 'from website',
  inferred: 'inferred',
};

interface TextAreaFieldProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  hint?: string;
  placeholder?: string;
  source?: FieldSource;
  userEdited?: boolean;
  rows?: number;
}

export default function TextAreaField({
  label,
  value,
  onChange,
  hint,
  placeholder,
  source,
  userEdited,
  rows = 4,
}: TextAreaFieldProps) {
  const id = useId();
  const showChip = source && !userEdited;
  return (
    <label htmlFor={id} className="flex flex-col text-sm">
      <span className="kicker mb-2 flex items-center gap-2">
        {label}
        {showChip && (
          <span className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">
            {SOURCE_LABELS[source]}
          </span>
        )}
      </span>
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="border border-rule bg-paper px-3 py-2 text-base leading-relaxed text-ink focus:border-ink focus:outline-none"
      />
      {hint && <span className="mt-1 text-xs italic text-muted">{hint}</span>}
    </label>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- TextAreaField`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/TextAreaField.tsx packages/web/src/components/openorg/guided/fields/TextAreaField.test.tsx
git commit -m "feat(openorg): add guided TextAreaField component"
```

---

## Task 2.3 — PillPicker

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/PillPicker.tsx`
- Create: `packages/web/src/components/openorg/guided/fields/PillPicker.test.tsx`

A pill row with two flavours (multi-select vs single-select). Soft selection cap with an inline nudge when exceeded.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/fields/PillPicker.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PillPicker from './PillPicker';

const VOCAB = [
  { key: 'older_people', label: 'Older people' },
  { key: 'children', label: 'Children & families' },
  { key: 'homelessness', label: 'Homelessness' },
];

describe('PillPicker', () => {
  it('renders one pill per option', () => {
    render(<PillPicker label="Themes" options={VOCAB} value={[]} onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /older people/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /homelessness/i })).toBeInTheDocument();
  });

  it('toggles a selection on click (multi-select)', () => {
    const onChange = vi.fn();
    render(<PillPicker label="Themes" options={VOCAB} value={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /older people/i }));
    expect(onChange).toHaveBeenCalledWith(['older_people']);
  });

  it('deselects when clicking an already-selected pill', () => {
    const onChange = vi.fn();
    render(
      <PillPicker
        label="Themes"
        options={VOCAB}
        value={['older_people']}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /older people/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('single-select replaces the prior value', () => {
    const onChange = vi.fn();
    render(
      <PillPicker
        label="Status"
        options={VOCAB}
        value={['older_people']}
        onChange={onChange}
        selectionCap={1}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /homelessness/i }));
    expect(onChange).toHaveBeenCalledWith(['homelessness']);
  });

  it('shows the cap nudge when a multi-select cap is exceeded and does not emit', () => {
    const onChange = vi.fn();
    const SIX = VOCAB.concat(
      ['a', 'b', 'c', 'd', 'e'].map((k) => ({ key: k, label: k })),
    );
    render(
      <PillPicker
        label="Themes"
        options={SIX}
        value={['older_people', 'children', 'homelessness', 'a', 'b', 'c']}
        onChange={onChange}
        selectionCap={6}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^d$/i }));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/six is plenty/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- PillPicker`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/fields/PillPicker.tsx
import { useState } from 'react';

export interface PillOption {
  key: string;
  label: string;
}

interface PillPickerProps {
  label: string;
  options: PillOption[];
  value: string[];
  onChange: (next: string[]) => void;
  /** Multi-select unless ``selectionCap === 1`` (radio behaviour). */
  selectionCap?: number;
  hint?: string;
}

export default function PillPicker({
  label,
  options,
  value,
  onChange,
  selectionCap,
  hint,
}: PillPickerProps) {
  const [capNudge, setCapNudge] = useState(false);

  const isSelected = (key: string) => value.includes(key);
  const handleClick = (key: string) => {
    if (selectionCap === 1) {
      onChange([key]);
      return;
    }
    if (isSelected(key)) {
      onChange(value.filter((v) => v !== key));
      setCapNudge(false);
      return;
    }
    if (selectionCap !== undefined && value.length >= selectionCap) {
      setCapNudge(true);
      return;
    }
    onChange([...value, key]);
  };

  return (
    <div className="flex flex-col text-sm">
      <span className="kicker mb-2">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const sel = isSelected(opt.key);
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => handleClick(opt.key)}
              aria-pressed={sel}
              className={`border px-3 py-1 text-xs uppercase tracking-wider transition ${
                sel
                  ? 'border-ink bg-ink text-paper'
                  : 'border-rule bg-paper text-muted hover:border-ink/40 hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {capNudge && (
        <span className="mt-2 text-xs italic text-muted">
          Six is plenty — uncheck one first.
        </span>
      )}
      {hint && !capNudge && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- PillPicker`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/PillPicker.tsx packages/web/src/components/openorg/guided/fields/PillPicker.test.tsx
git commit -m "feat(openorg): add guided PillPicker component"
```

---

## Task 2.4 — CardList

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/CardList.tsx`
- Create: `packages/web/src/components/openorg/guided/fields/CardList.test.tsx`

Repeating items rendered as a stack of cards. Each card expands on click; "+ Add" appends a fresh item. Removal via an explicit Remove button on the expanded card.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/fields/CardList.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CardList from './CardList';

const SHAPE = [
  { key: 'name', label: 'Name', kind: 'text' as const },
  { key: 'description', label: 'Description', kind: 'textarea' as const },
];

describe('CardList', () => {
  it('renders one card per item with a title preview', () => {
    render(
      <CardList
        label="Programmes"
        value={[
          { name: 'Foodbank', description: 'A network.' },
          { name: 'Helpline', description: 'Phone support.' },
        ]}
        shape={SHAPE}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText('Foodbank')).toBeInTheDocument();
    expect(screen.getByText('Helpline')).toBeInTheDocument();
  });

  it('adds a blank item on Add', () => {
    const onChange = vi.fn();
    render(<CardList label="Programmes" value={[]} shape={SHAPE} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /add/i }));
    expect(onChange).toHaveBeenCalledWith([{ name: '', description: '' }]);
  });

  it('emits the updated item when a field changes', () => {
    const onChange = vi.fn();
    render(
      <CardList
        label="Programmes"
        value={[{ name: 'Foodbank', description: '' }]}
        shape={SHAPE}
        onChange={onChange}
      />,
    );
    // Cards start collapsed; click to expand.
    fireEvent.click(screen.getByText('Foodbank'));
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Foodbank network' } });
    expect(onChange).toHaveBeenLastCalledWith([
      { name: 'Foodbank network', description: '' },
    ]);
  });

  it('removes an item via the Remove button', () => {
    const onChange = vi.fn();
    render(
      <CardList
        label="Programmes"
        value={[{ name: 'A' }, { name: 'B' }]}
        shape={[{ key: 'name', label: 'Name', kind: 'text' }]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText('A'));
    fireEvent.click(screen.getAllByRole('button', { name: /remove/i })[0]);
    expect(onChange).toHaveBeenCalledWith([{ name: 'B' }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- CardList`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/fields/CardList.tsx
import { useState } from 'react';
import TextField from './TextField';
import TextAreaField from './TextAreaField';
import type { FieldDef } from '../sections/profile';

interface CardListProps {
  label: string;
  value: any[];
  shape: FieldDef[];
  onChange: (next: any[]) => void;
  hint?: string;
}

function titleOf(item: any, shape: FieldDef[]): string {
  for (const f of shape) {
    if (typeof item?.[f.key] === 'string' && item[f.key].trim()) {
      return item[f.key].slice(0, 80);
    }
  }
  return '(untitled)';
}

function blankItem(shape: FieldDef[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of shape) out[f.key] = '';
  return out;
}

export default function CardList({ label, value, shape, onChange, hint }: CardListProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  const handleFieldChange = (idx: number, key: string, next: string) => {
    const updated = value.map((item, i) => (i === idx ? { ...item, [key]: next } : item));
    onChange(updated);
  };

  const handleAdd = () => {
    onChange([...value, blankItem(shape)]);
    setOpenIdx(value.length);
  };

  const handleRemove = (idx: number) => {
    onChange(value.filter((_, i) => i !== idx));
    setOpenIdx(null);
  };

  return (
    <div className="flex flex-col text-sm">
      <span className="kicker mb-2">{label}</span>
      <ul className="flex flex-col gap-2">
        {value.map((item, idx) => {
          const open = idx === openIdx;
          return (
            <li key={idx} className="border border-rule bg-paper">
              <button
                type="button"
                onClick={() => setOpenIdx(open ? null : idx)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-ink hover:bg-paper-2"
                aria-expanded={open}
              >
                <span>{titleOf(item, shape)}</span>
                <span className="text-xs text-muted">{open ? 'Close' : 'Edit'}</span>
              </button>
              {open && (
                <div className="flex flex-col gap-3 border-t border-rule px-3 py-3">
                  {shape.map((f) => {
                    if (f.kind === 'textarea') {
                      return (
                        <TextAreaField
                          key={f.key}
                          label={f.label}
                          value={item?.[f.key] ?? ''}
                          onChange={(next) => handleFieldChange(idx, f.key, next)}
                        />
                      );
                    }
                    return (
                      <TextField
                        key={f.key}
                        label={f.label}
                        value={item?.[f.key] ?? ''}
                        onChange={(next) => handleFieldChange(idx, f.key, next)}
                      />
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => handleRemove(idx)}
                    className="self-start border border-rule px-3 py-1 text-xs uppercase tracking-wider text-muted hover:text-red-900"
                  >
                    Remove
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        onClick={handleAdd}
        className="mt-3 self-start border border-rule bg-paper-2 px-3 py-1 text-xs uppercase tracking-wider text-ink hover:bg-paper"
      >
        + Add
      </button>
      {hint && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- CardList`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/CardList.tsx packages/web/src/components/openorg/guided/fields/CardList.test.tsx
git commit -m "feat(openorg): add guided CardList component"
```

---

## Task 2.5 — GroupRule

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/GroupRule.tsx`
- Create: `packages/web/src/components/openorg/guided/fields/GroupRule.test.tsx`

Visual cluster for related fields (e.g. Place = description + area codes + geolocation). Dashed top border + small caption + children below.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/fields/GroupRule.test.tsx
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import GroupRule from './GroupRule';

describe('GroupRule', () => {
  it('renders the caption and children', () => {
    render(
      <GroupRule caption="Place">
        <div>child A</div>
        <div>child B</div>
      </GroupRule>,
    );
    expect(screen.getByText('Place')).toBeInTheDocument();
    expect(screen.getByText('child A')).toBeInTheDocument();
    expect(screen.getByText('child B')).toBeInTheDocument();
  });

  it('renders a dashed top border on the wrapper', () => {
    const { container } = render(
      <GroupRule caption="Place">
        <span />
      </GroupRule>,
    );
    const wrap = container.firstElementChild as HTMLElement;
    expect(wrap.className).toMatch(/border-dashed/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- GroupRule`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/fields/GroupRule.tsx
import type { ReactNode } from 'react';

interface GroupRuleProps {
  caption: string;
  children: ReactNode;
}

export default function GroupRule({ caption, children }: GroupRuleProps) {
  return (
    <div className="mt-4 border-t border-dashed border-rule pt-3">
      <div className="kicker mb-3 text-muted">{caption}</div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- GroupRule`
Expected: PASS.

- [ ] **Step 5: Commit + PR gate**

```bash
git add packages/web/src/components/openorg/guided/fields/GroupRule.tsx packages/web/src/components/openorg/guided/fields/GroupRule.test.tsx
git commit -m "feat(openorg): add guided GroupRule component"

cd packages/web && npm run build && npm run lint && npm test
```

Expected: all green. Open PR 2 (`editor-polish-pr2-fields`).

---

# PR 3 — GuidedEditor + EditorShell + EditProfile wrap

Goal: assemble the field components into a working GuidedEditor and a SurfaceSwitch-controlled EditorShell. Wrap EditProfile only — the other three editors come in PR 4.

Pre-flight: branch `editor-polish-pr3-shell` off `master` (after PR 2 lands).

## Task 3.1 — SidebarNav

**Files:**
- Create: `packages/web/src/components/openorg/guided/SidebarNav.tsx`
- Create: `packages/web/src/components/openorg/guided/SidebarNav.test.tsx`

Left rail: section list with tick state, "X% done" rollup, and a "Missing" panel.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/SidebarNav.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SidebarNav from './SidebarNav';

const SECTIONS = [
  { id: 'a', name: 'Alpha', tick: '✓' as const, missing: [] },
  { id: 'b', name: 'Beta', tick: '●' as const, missing: ['summary'] },
  { id: 'c', name: 'Gamma', tick: '○' as const, missing: ['everything'] },
];

describe('SidebarNav', () => {
  it('renders one row per section with its tick', () => {
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={vi.fn()} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
    expect(screen.getAllByText('✓').length).toBeGreaterThan(0);
  });

  it('shows the completion rollup', () => {
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={vi.fn()} />);
    // 1 of 3 complete = 33%.
    expect(screen.getByText(/33% done/i)).toBeInTheDocument();
  });

  it('calls onSelect with the clicked id', () => {
    const onSelect = vi.fn();
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /beta/i }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });

  it('lists missing items, click-jump fires onSelect', () => {
    const onSelect = vi.fn();
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /beta — summary/i }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- SidebarNav`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/SidebarNav.tsx
export type Tick = '✓' | '●' | '○';

export interface SidebarSectionState {
  id: string;
  name: string;
  tick: Tick;
  missing: string[];
}

interface SidebarNavProps {
  sections: SidebarSectionState[];
  activeId: string;
  onSelect: (id: string) => void;
  /** Optional "Start here" badge on a specific section id, set by the welcome strip. */
  startHereId?: string;
}

function rollup(sections: SidebarSectionState[]): number {
  if (sections.length === 0) return 100;
  const done = sections.filter((s) => s.tick === '✓').length;
  return Math.round((done / sections.length) * 100);
}

export default function SidebarNav({
  sections,
  activeId,
  onSelect,
  startHereId,
}: SidebarNavProps) {
  const pct = rollup(sections);
  const missing = sections.filter((s) => s.missing.length > 0);

  return (
    <nav aria-label="Editor sections" className="flex flex-col gap-4">
      <ul className="flex flex-col">
        {sections.map((s) => {
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSelect(s.id)}
                className={`flex w-full items-center justify-between border-l-2 px-3 py-2 text-left text-sm transition ${
                  isActive
                    ? 'border-ink bg-paper-2 text-ink'
                    : 'border-transparent text-muted hover:bg-paper-2/60 hover:text-ink'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span aria-hidden className="font-mono text-xs">
                    {s.tick}
                  </span>
                  <span>{s.name}</span>
                </span>
                {startHereId === s.id && (
                  <span className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">
                    Start here
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-rule pt-3 text-xs text-muted">
        <div className="kicker">{pct}% done</div>
        {missing.length > 0 && (
          <div className="mt-3">
            <div className="kicker mb-2">Missing</div>
            <ul className="flex flex-col gap-1">
              {missing.map((s) =>
                s.missing.map((m) => (
                  <li key={`${s.id}-${m}`}>
                    <button
                      type="button"
                      onClick={() => onSelect(s.id)}
                      className="text-left text-[11px] text-muted hover:text-ink"
                    >
                      · {s.name} — {m}
                    </button>
                  </li>
                )),
              )}
            </ul>
          </div>
        )}
      </div>
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- SidebarNav`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/SidebarNav.tsx packages/web/src/components/openorg/guided/SidebarNav.test.tsx
git commit -m "feat(openorg): add guided SidebarNav with tick states and missing panel"
```

---

## Task 3.2 — Section component

**Files:**
- Create: `packages/web/src/components/openorg/guided/Section.tsx`
- Create: `packages/web/src/components/openorg/guided/Section.test.tsx`

Middle column: renders one section's fields based on its spec, against a `ParsedSection`. Emits per-field changes back to the parent.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/Section.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Section from './Section';
import { PROFILE_SECTIONS } from './sections/profile';

const identity = PROFILE_SECTIONS.find((s) => s.id === 'identity')!;

describe('Section', () => {
  it('renders the section heading and field labels', () => {
    render(
      <Section
        section={identity}
        parsed={{ yaml: { identity: { name: '' } }, body: {} }}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/identity/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument();
  });

  it('emits a parsed update on text-field change', () => {
    const onChange = vi.fn();
    render(
      <Section
        section={identity}
        parsed={{ yaml: { identity: { name: '' } }, body: {} }}
        onChange={onChange}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    const lastCall = onChange.mock.calls.at(-1)![0];
    expect(lastCall.yaml.identity.name).toBe('Trussell');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- Section.test`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/Section.tsx
import TextField from './fields/TextField';
import TextAreaField from './fields/TextAreaField';
import PillPicker, { type PillOption } from './fields/PillPicker';
import CardList from './fields/CardList';
import GroupRule from './fields/GroupRule';
import type { ParsedSection } from './bridge';
import type { FieldDef, GuidedSection } from './sections/profile';

interface SectionProps {
  section: GuidedSection;
  parsed: ParsedSection;
  onChange: (next: ParsedSection) => void;
  vocabs: Record<string, PillOption[]>;
}

function getByPath(parsed: ParsedSection, key: string): any {
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    let cursor: any = parsed.yaml[head];
    for (const part of rest) {
      if (cursor == null) return undefined;
      cursor = cursor[part];
    }
    return cursor;
  }
  // Body section: key is a heading.
  if (parsed.body[key] !== undefined) return parsed.body[key];
  // Top-level yaml key.
  return parsed.yaml[key];
}

function setByPath(parsed: ParsedSection, key: string, value: any): ParsedSection {
  const next: ParsedSection = {
    yaml: { ...parsed.yaml },
    body: { ...parsed.body },
  };
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    const headObj = { ...(next.yaml[head] ?? {}) };
    let cursor: any = headObj;
    for (let i = 0; i < rest.length - 1; i += 1) {
      cursor[rest[i]] = { ...(cursor[rest[i]] ?? {}) };
      cursor = cursor[rest[i]];
    }
    cursor[rest[rest.length - 1]] = value;
    next.yaml[head] = headObj;
    return next;
  }
  // If the key matches a body heading from the section spec, write to body.
  if (parsed.body[key] !== undefined || /\s/.test(key) || key[0] === key[0].toUpperCase()) {
    // Heuristic: body headings have spaces or start uppercase; yaml top-level keys are snake_case lowercase.
    if (key === key.toLowerCase() && !/\s/.test(key)) {
      next.yaml[key] = value;
    } else {
      next.body[key] = value;
    }
    return next;
  }
  next.yaml[key] = value;
  return next;
}

function renderField(
  field: FieldDef,
  parsed: ParsedSection,
  onChange: (next: ParsedSection) => void,
  vocabs: Record<string, PillOption[]>,
): JSX.Element {
  const value = getByPath(parsed, field.key);

  if (field.kind === 'text') {
    return (
      <TextField
        key={field.key}
        label={field.label}
        value={value ?? ''}
        hint={field.hint}
        placeholder={field.placeholder}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'textarea') {
    return (
      <TextAreaField
        key={field.key}
        label={field.label}
        value={value ?? ''}
        hint={field.hint}
        placeholder={field.placeholder}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'pills') {
    const options = (field.vocab && vocabs[field.vocab]) ?? [];
    return (
      <PillPicker
        key={field.key}
        label={field.label}
        options={options}
        value={Array.isArray(value) ? value : value ? [value] : []}
        hint={field.hint}
        selectionCap={field.selectionCap}
        onChange={(v) =>
          onChange(setByPath(parsed, field.key, field.selectionCap === 1 ? v[0] ?? '' : v))
        }
      />
    );
  }
  if (field.kind === 'card-list') {
    return (
      <CardList
        key={field.key}
        label={field.label}
        value={Array.isArray(value) ? value : []}
        shape={field.cardShape ?? []}
        hint={field.hint}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'group') {
    return (
      <GroupRule key={field.key} caption={field.label}>
        {(field.children ?? []).map((child) => {
          const childKey = `${field.key}.${child.key}`;
          const childValue = getByPath(parsed, childKey);
          if (child.kind === 'textarea') {
            return (
              <TextAreaField
                key={childKey}
                label={child.label}
                value={childValue ?? ''}
                onChange={(v) => onChange(setByPath(parsed, childKey, v))}
              />
            );
          }
          if (child.kind === 'card-list') {
            return (
              <CardList
                key={childKey}
                label={child.label}
                value={Array.isArray(childValue) ? childValue : []}
                shape={child.cardShape ?? []}
                onChange={(v) => onChange(setByPath(parsed, childKey, v))}
              />
            );
          }
          if (child.kind === 'group') {
            return (
              <GroupRule key={childKey} caption={child.label}>
                {(child.children ?? []).map((grand) => {
                  const grandKey = `${childKey}.${grand.key}`;
                  const grandValue = getByPath(parsed, grandKey);
                  return (
                    <TextField
                      key={grandKey}
                      label={grand.label}
                      value={grandValue ?? ''}
                      onChange={(v) => onChange(setByPath(parsed, grandKey, v))}
                    />
                  );
                })}
              </GroupRule>
            );
          }
          return (
            <TextField
              key={childKey}
              label={child.label}
              value={childValue ?? ''}
              onChange={(v) => onChange(setByPath(parsed, childKey, v))}
            />
          );
        })}
      </GroupRule>
    );
  }
  return <span key={field.key}>Unsupported field kind: {field.kind}</span>;
}

function sectionIsEmpty(section: GuidedSection, parsed: ParsedSection): boolean {
  return section.fields.every((f) => {
    const v = getByPath(parsed, f.key);
    if (v == null) return true;
    if (typeof v === 'string') return v.trim() === '';
    if (Array.isArray(v)) return v.length === 0;
    if (typeof v === 'object') return Object.values(v).every((x) => x == null || x === '');
    return false;
  });
}

export default function Section({ section, parsed, onChange, vocabs }: SectionProps) {
  const empty = sectionIsEmpty(section, parsed);
  return (
    <section className="flex flex-col gap-4" data-section-id={section.id}>
      <header>
        <div className="kicker">{section.name}</div>
        <p className="mt-1 max-w-prose text-sm text-muted">{section.description}</p>
      </header>
      {empty && section.emptyPrompt && (
        <p className="max-w-prose border-l-2 border-rule pl-3 text-sm italic text-muted">
          {section.emptyPrompt}
        </p>
      )}
      <div className="flex flex-col gap-4">
        {section.fields.map((f) => renderField(f, parsed, onChange, vocabs))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- Section.test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/Section.tsx packages/web/src/components/openorg/guided/Section.test.tsx
git commit -m "feat(openorg): add guided Section component"
```

---

## Task 3.3 — SurfaceSwitch

**Files:**
- Create: `packages/web/src/components/openorg/SurfaceSwitch.tsx`
- Create: `packages/web/src/components/openorg/SurfaceSwitch.test.tsx`

Two-button segmented toggle (Guided · Markdown) that persists choice to localStorage per record kind.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/SurfaceSwitch.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SurfaceSwitch, { useEditorSurface } from './SurfaceSwitch';

describe('useEditorSurface', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('defaults to guided when no value is set', () => {
    function Probe() {
      const [s] = useEditorSurface('profile');
      return <span>{s}</span>;
    }
    render(<Probe />);
    expect(screen.getByText('guided')).toBeInTheDocument();
  });

  it('persists per record kind and reads on remount', () => {
    function Probe({ kind }: { kind: 'profile' | 'strategy' }) {
      const [s, setS] = useEditorSurface(kind);
      return (
        <div>
          <span data-testid="val">{s}</span>
          <button type="button" onClick={() => setS('markdown')}>set md</button>
        </div>
      );
    }
    const { unmount, getByTestId, getByRole } = render(<Probe kind="profile" />);
    fireEvent.click(getByRole('button', { name: /set md/i }));
    expect(getByTestId('val').textContent).toBe('markdown');
    unmount();

    // Strategy is still default-guided.
    const s = render(<Probe kind="strategy" />);
    expect(s.getByTestId('val').textContent).toBe('guided');
    s.unmount();

    // Profile remembers markdown.
    const p = render(<Probe kind="profile" />);
    expect(p.getByTestId('val').textContent).toBe('markdown');
  });
});

describe('SurfaceSwitch', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('renders both options and calls onChange', () => {
    const onChange = vi.fn();
    render(<SurfaceSwitch value="guided" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /markdown/i }));
    expect(onChange).toHaveBeenCalledWith('markdown');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- SurfaceSwitch`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/SurfaceSwitch.tsx
import { useEffect, useState } from 'react';

export type EditorSurface = 'guided' | 'markdown';
export type RecordKind = 'profile' | 'strategy' | 'idea';

const KEY = (kind: RecordKind) => `openorg.editorSurface.${kind}`;

function readSurface(kind: RecordKind): EditorSurface {
  if (typeof window === 'undefined') return 'guided';
  const v = window.localStorage.getItem(KEY(kind));
  return v === 'markdown' ? 'markdown' : 'guided';
}

export function useEditorSurface(kind: RecordKind): [EditorSurface, (s: EditorSurface) => void] {
  const [surface, setSurface] = useState<EditorSurface>(() => readSurface(kind));
  useEffect(() => {
    setSurface(readSurface(kind));
  }, [kind]);
  const update = (s: EditorSurface) => {
    setSurface(s);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(KEY(kind), s);
    }
  };
  return [surface, update];
}

interface SurfaceSwitchProps {
  value: EditorSurface;
  onChange: (next: EditorSurface) => void;
}

export default function SurfaceSwitch({ value, onChange }: SurfaceSwitchProps) {
  return (
    <div role="group" aria-label="Editor surface" className="inline-flex border border-rule text-xs">
      <button
        type="button"
        onClick={() => onChange('guided')}
        aria-pressed={value === 'guided'}
        className={`px-3 py-1 uppercase tracking-wider transition ${
          value === 'guided' ? 'bg-ink text-paper' : 'bg-paper text-muted hover:text-ink'
        }`}
      >
        Guided
      </button>
      <button
        type="button"
        onClick={() => onChange('markdown')}
        aria-pressed={value === 'markdown'}
        className={`px-3 py-1 uppercase tracking-wider transition ${
          value === 'markdown' ? 'bg-ink text-paper' : 'bg-paper text-muted hover:text-ink'
        }`}
      >
        Markdown
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- SurfaceSwitch`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/SurfaceSwitch.tsx packages/web/src/components/openorg/SurfaceSwitch.test.tsx
git commit -m "feat(openorg): add SurfaceSwitch with per-kind localStorage"
```

---

## Task 3.4 — GuidedEditor

**Files:**
- Create: `packages/web/src/components/openorg/guided/GuidedEditor.tsx`
- Create: `packages/web/src/components/openorg/guided/GuidedEditor.test.tsx`
- Create: `packages/web/src/components/openorg/guided/tickState.ts`

Composes SidebarNav + Section + preview. Holds the parsed-source state, threads edits through the bridge, and surfaces tick state to the sidebar.

- [ ] **Step 1: Write `tickState.ts` first (small helper, failing test inline)**

```typescript
// packages/web/src/components/openorg/guided/tickState.test.ts
import { describe, expect, it } from 'vitest';
import { computeTickStates } from './tickState';
import { PROFILE_SECTIONS } from './sections/profile';

describe('computeTickStates', () => {
  it('marks identity ✓ when all required identity fields are non-empty', () => {
    const source = `---\nidentity:\n  name: Trust\n  website: https://x.org\n  founded: 1990\n  contact:\n    email: a@b.c\n    phone: '123'\n  geography:\n    description: Norfolk\n    primary_area: E07000148\n  scale: regional\n  also_known_as:\n    - value: T\n---\n`;
    const ticks = computeTickStates(source, PROFILE_SECTIONS);
    const identity = ticks.find((t) => t.id === 'identity')!;
    expect(identity.tick).toBe('✓');
  });

  it('marks empty section ○', () => {
    const source = `---\n---\n`;
    const ticks = computeTickStates(source, PROFILE_SECTIONS);
    expect(ticks.find((t) => t.id === 'identity')!.tick).toBe('○');
  });

  it('marks partial section ●', () => {
    const source = `---\nidentity:\n  name: Trust\n---\n`;
    const ticks = computeTickStates(source, PROFILE_SECTIONS);
    expect(ticks.find((t) => t.id === 'identity')!.tick).toBe('●');
  });
});
```

```typescript
// packages/web/src/components/openorg/guided/tickState.ts
import { parseSection } from './bridge';
import type { GuidedSection } from './sections/profile';
import type { SidebarSectionState } from './SidebarNav';

function isFilled(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).some(isFilled);
  return true;
}

function fieldValue(parsed: ReturnType<typeof parseSection>, key: string): unknown {
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    let cursor: any = parsed.yaml[head];
    for (const part of rest) {
      if (cursor == null) return undefined;
      cursor = cursor[part];
    }
    return cursor;
  }
  if (parsed.body[key] !== undefined) return parsed.body[key];
  return parsed.yaml[key];
}

export function computeTickStates(
  source: string,
  sections: GuidedSection[],
): SidebarSectionState[] {
  return sections.map((section) => {
    const parsed = parseSection(source, section);
    const fieldsFilled = section.fields.map((f) => isFilled(fieldValue(parsed, f.key)));
    const filled = fieldsFilled.filter(Boolean).length;
    const missing = section.fields
      .filter((_, i) => !fieldsFilled[i])
      .map((f) => f.label.toLowerCase());
    let tick: '✓' | '●' | '○';
    if (filled === 0) tick = '○';
    else if (filled === section.fields.length) tick = '✓';
    else tick = '●';
    return { id: section.id, name: section.name, tick, missing };
  });
}
```

Run: `cd packages/web && npm test -- tickState`
Expected: PASS.

```bash
git add packages/web/src/components/openorg/guided/tickState.ts packages/web/src/components/openorg/guided/tickState.test.ts
git commit -m "feat(openorg): compute tick states from parsed sections"
```

- [ ] **Step 2: Write the failing test for GuidedEditor**

```typescript
// packages/web/src/components/openorg/guided/GuidedEditor.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import GuidedEditor from './GuidedEditor';
import { PROFILE_SECTIONS } from './sections/profile';

const SOURCE = `---
schema_version: open-org/v0.1
identity:
  name: Trust
---

## Mission

We do good.
`;

describe('GuidedEditor', () => {
  it('renders sidebar entries for each section', () => {
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByRole('button', { name: /identity/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /mission/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /values/i })).toBeInTheDocument();
  });

  it('shows the active section in the middle column', () => {
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByLabelText(/^name$/i)).toHaveValue('Trust');
  });

  it('writes back through the bridge on field edit', () => {
    const onChange = vi.fn();
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={onChange}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    const updatedSource = onChange.mock.calls.at(-1)![0] as string;
    expect(updatedSource).toContain('name: Trussell');
    // Body untouched.
    expect(updatedSource).toContain('## Mission\n\nWe do good.');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/web && npm test -- GuidedEditor.test`
Expected: FAIL — module not found.

- [ ] **Step 4: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/guided/GuidedEditor.tsx
import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SidebarNav from './SidebarNav';
import Section from './Section';
import { applySectionEdit, parseSection, type ParsedSection } from './bridge';
import { computeTickStates } from './tickState';
import type { GuidedSection } from './sections/profile';
import type { PillOption } from './fields/PillPicker';

interface GuidedEditorProps {
  source: string;
  sections: GuidedSection[];
  onChange: (nextSource: string) => void;
  vocabs: Record<string, PillOption[]>;
  startHereId?: string;
}

function splitFrontmatterPreview(src: string): { frontmatter: string; body: string } {
  if (!src.startsWith('---\n') && !src.startsWith('---\r\n')) return { frontmatter: '', body: src };
  const closing = src.indexOf('\n---', 4);
  if (closing === -1) return { frontmatter: src, body: '' };
  return { frontmatter: src.slice(0, closing + 4), body: src.slice(closing + 4).replace(/^\r?\n/, '') };
}

export default function GuidedEditor({
  source,
  sections,
  onChange,
  vocabs,
  startHereId,
}: GuidedEditorProps) {
  const [activeId, setActiveId] = useState(sections[0]?.id ?? '');
  const ticks = useMemo(() => computeTickStates(source, sections), [source, sections]);
  const active = sections.find((s) => s.id === activeId) ?? sections[0];
  const parsed: ParsedSection = useMemo(() => parseSection(source, active), [source, active]);
  const { body } = useMemo(() => splitFrontmatterPreview(source), [source]);

  const handleSectionChange = (next: ParsedSection) => {
    onChange(applySectionEdit(source, active, next));
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[14rem_minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="lg:border-r lg:border-rule lg:pr-4">
        <SidebarNav
          sections={ticks}
          activeId={active.id}
          onSelect={setActiveId}
          startHereId={startHereId}
        />
      </aside>
      <div>
        <Section section={active} parsed={parsed} onChange={handleSectionChange} vocabs={vocabs} />
      </div>
      <div className="border-l border-rule pl-4 lg:overflow-auto">
        <div className="kicker mb-2">Preview</div>
        <article className="editorial-preview text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd packages/web && npm test -- GuidedEditor.test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/web/src/components/openorg/guided/GuidedEditor.tsx packages/web/src/components/openorg/guided/GuidedEditor.test.tsx
git commit -m "feat(openorg): assemble GuidedEditor with sidebar, section, and preview"
```

---

## Task 3.5 — EditorShell

**Files:**
- Create: `packages/web/src/components/openorg/EditorShell.tsx`
- Create: `packages/web/src/components/openorg/EditorShell.test.tsx`

Wraps a record. Holds the source string, switches between GuidedEditor and MarkdownEditor, places the SurfaceSwitch top-right.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/EditorShell.test.tsx
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import EditorShell from './EditorShell';
import { PROFILE_SECTIONS } from './guided/sections/profile';

const SOURCE = `---
identity:
  name: Trust
---

## Mission

x
`;

describe('EditorShell', () => {
  beforeEach(() => window.localStorage.clear());

  it('renders the guided surface by default', () => {
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    // Guided surface has sidebar buttons.
    expect(screen.getByRole('button', { name: /^identity/i })).toBeInTheDocument();
  });

  it('switches to markdown surface and persists', () => {
    const { unmount } = render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^markdown$/i }));
    expect(screen.getByText(/^source$/i)).toBeInTheDocument();
    unmount();

    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/^source$/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- EditorShell`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/EditorShell.tsx
import { useEffect, useState } from 'react';
import MarkdownEditor from './MarkdownEditor';
import GuidedEditor from './guided/GuidedEditor';
import SurfaceSwitch, { useEditorSurface, type RecordKind } from './SurfaceSwitch';
import type { GuidedSection } from './guided/sections/profile';
import type { PillOption } from './guided/fields/PillPicker';
import type { ValidationFieldError } from '../../api/openorg';

interface EditorShellProps {
  kind: RecordKind;
  initialSource: string;
  sections: GuidedSection[];
  onSave: (markdown: string) => Promise<unknown>;
  vocabs: Record<string, PillOption[]>;
  saving?: boolean;
  validationErrors?: ValidationFieldError[];
  saveLabel?: string;
  startHereId?: string;
}

export default function EditorShell({
  kind,
  initialSource,
  sections,
  onSave,
  vocabs,
  saving = false,
  validationErrors = [],
  saveLabel = 'Save',
  startHereId,
}: EditorShellProps) {
  const [surface, setSurface] = useEditorSurface(kind);
  const [source, setSource] = useState(initialSource);

  useEffect(() => {
    setSource(initialSource);
  }, [initialSource]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end">
        <SurfaceSwitch value={surface} onChange={setSurface} />
      </div>

      {surface === 'guided' ? (
        <GuidedEditor
          source={source}
          sections={sections}
          onChange={setSource}
          vocabs={vocabs}
          startHereId={startHereId}
        />
      ) : (
        <MarkdownEditor
          initialMarkdown={source}
          onSave={async (md) => {
            setSource(md);
            return onSave(md);
          }}
          saving={saving}
          validationErrors={validationErrors}
          saveLabel={saveLabel}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- EditorShell`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/EditorShell.tsx packages/web/src/components/openorg/EditorShell.test.tsx
git commit -m "feat(openorg): add EditorShell dual-surface wrapper"
```

---

## Task 3.6 — Wire EditProfile through EditorShell

**Files:**
- Modify: `packages/web/src/pages/openorg/EditProfile.tsx`
- Modify: `packages/web/src/pages/openorg/EditProfile.test.tsx`

Swap the bare `MarkdownEditor` for `EditorShell` with `PROFILE_SECTIONS`. Vocabs are stubbed `{}` for now — wired in PR 4 once we have a themes hook output that the editor can consume.

- [ ] **Step 1: Update the existing test**

Edit `packages/web/src/pages/openorg/EditProfile.test.tsx` — append a new case:

```typescript
  it('renders the guided sidebar by default when source has frontmatter', () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\nidentity:\n  name: A\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');
    expect(screen.getByRole('button', { name: /^identity/i })).toBeInTheDocument();
  });
```

Run: `cd packages/web && npm test -- EditProfile.test`
Expected: existing tests pass; the new test FAILS (`identity` button not in DOM yet).

- [ ] **Step 2: Modify `EditProfile.tsx`**

Replace the `<MarkdownEditor … />` call with:

```typescript
import EditorShell from '../../components/openorg/EditorShell';
import { PROFILE_SECTIONS } from '../../components/openorg/guided/sections/profile';
```

```typescript
        <EditorShell
          kind="profile"
          initialSource={profile.data?.markdown ?? ''}
          sections={PROFILE_SECTIONS}
          onSave={handleSave}
          vocabs={{}}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save profile"
        />
```

Leave the unused `MarkdownEditor` import removed. Keep `PublishBadge`/`PublishControls` — they get replaced in PR 4.

- [ ] **Step 3: Run all editor tests**

Run: `cd packages/web && npm test -- EditProfile`
Expected: PASS.

- [ ] **Step 4: Build + lint**

Run: `cd packages/web && npm run build && npm run lint`
Expected: green.

- [ ] **Step 5: Commit + PR gate**

```bash
git add packages/web/src/pages/openorg/EditProfile.tsx packages/web/src/pages/openorg/EditProfile.test.tsx
git commit -m "feat(openorg): wrap EditProfile in EditorShell"

cd packages/web && npm test
```

Open PR 3 (`editor-polish-pr3-shell`).

---

# PR 4 — Roll-out + autosave + PublishStrip

Goal: wrap the remaining three editors in EditorShell; add SaveIndicator + autosave for the Guided surface; replace `PublishControls` with `PublishStrip` (inline confirm + celebratory moment); wire `themes` vocab from the existing `useThemes` hook.

Pre-flight: branch `editor-polish-pr4-publish` off `master` (after PR 3 lands).

## Task 4.1 — SaveIndicator

**Files:**
- Create: `packages/web/src/components/openorg/SaveIndicator.tsx`
- Create: `packages/web/src/components/openorg/SaveIndicator.test.tsx`

Header status: Saved (with relative age), Saving…, Couldn't save (+ Retry), Unsaved (markdown surface only).

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/SaveIndicator.test.tsx
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import SaveIndicator from './SaveIndicator';

describe('SaveIndicator', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('renders Saving while in flight', () => {
    render(<SaveIndicator state="saving" />);
    expect(screen.getByText(/saving/i)).toBeInTheDocument();
  });

  it('renders Saved · just now and ages over time', () => {
    render(<SaveIndicator state="saved" savedAt={new Date()} />);
    expect(screen.getByText(/just now/i)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(screen.getByText(/15s ago|14s ago|16s ago/i)).toBeInTheDocument();
  });

  it('renders the error state with a Retry button that calls onRetry', () => {
    const onRetry = vi.fn();
    render(<SaveIndicator state="error" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('renders Unsaved · ⌘S to save when given the unsaved state', () => {
    render(<SaveIndicator state="unsaved" />);
    expect(screen.getByText(/unsaved/i)).toBeInTheDocument();
    expect(screen.getByText(/⌘s/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- SaveIndicator`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/SaveIndicator.tsx
import { useEffect, useState } from 'react';

export type SaveState = 'saved' | 'saving' | 'error' | 'unsaved';

interface SaveIndicatorProps {
  state: SaveState;
  savedAt?: Date;
  onRetry?: () => void;
}

function ageLabel(savedAt: Date, now: number): string {
  const diffSec = Math.max(0, Math.round((now - savedAt.getTime()) / 1000));
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  return `${Math.round(diffSec / 3600)}h ago`;
}

export default function SaveIndicator({ state, savedAt, onRetry }: SaveIndicatorProps) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (state !== 'saved') return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(id);
  }, [state]);

  if (state === 'saving') {
    return (
      <span className="kicker text-muted" aria-live="polite">
        Saving…
      </span>
    );
  }
  if (state === 'error') {
    return (
      <span className="kicker text-red-900" aria-live="assertive">
        Couldn't save —{' '}
        <button
          type="button"
          onClick={onRetry}
          className="ml-1 border border-rule px-2 py-0.5 text-xs hover:bg-paper-2"
        >
          Retry
        </button>
      </span>
    );
  }
  if (state === 'unsaved') {
    return (
      <span className="kicker text-muted" aria-live="polite">
        Unsaved · <span className="ml-1 font-mono">⌘S</span> to save
      </span>
    );
  }
  const age = savedAt ? ageLabel(savedAt, now) : 'just now';
  return (
    <span className="kicker text-muted" aria-live="polite">
      Saved · {age}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- SaveIndicator`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/SaveIndicator.tsx packages/web/src/components/openorg/SaveIndicator.test.tsx
git commit -m "feat(openorg): add SaveIndicator with four states + age ticker"
```

---

## Task 4.2 — `useAutosave` hook

**Files:**
- Create: `packages/web/src/components/openorg/useAutosave.ts`
- Create: `packages/web/src/components/openorg/useAutosave.test.ts`

Debounced autosave: when `source` changes, wait 600ms, then call `save(source)`. Surfaces `state`, `savedAt`, and a `retry` callback for the indicator.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/useAutosave.test.ts
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAutosave } from './useAutosave';

describe('useAutosave', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('debounces saves by 600ms', async () => {
    const save = vi.fn(async () => undefined);
    const { rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    rerender({ source: 'c' });
    expect(save).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(599);
    });
    expect(save).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(2);
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('c');
  });

  it('sets state to saving then saved on success', async () => {
    let resolve: (() => void) | null = null;
    const save = vi.fn(
      () =>
        new Promise<void>((r) => {
          resolve = () => r();
        }),
    );
    const { result, rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    await act(async () => {
      vi.advanceTimersByTime(601);
    });
    expect(result.current.state).toBe('saving');
    await act(async () => {
      resolve!();
    });
    expect(result.current.state).toBe('saved');
    expect(result.current.savedAt).toBeInstanceOf(Date);
  });

  it('flips to error and exposes retry', async () => {
    let reject: ((e: Error) => void) | null = null;
    const save = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((_, r) => {
            reject = (e) => r(e);
          }),
      )
      .mockResolvedValueOnce(undefined);
    const { result, rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    await act(async () => {
      vi.advanceTimersByTime(601);
    });
    await act(async () => {
      reject!(new Error('boom'));
    });
    expect(result.current.state).toBe('error');
    await act(async () => {
      result.current.retry();
    });
    expect(save).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- useAutosave`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/useAutosave.ts
import { useCallback, useEffect, useRef, useState } from 'react';
import type { SaveState } from './SaveIndicator';

const DEBOUNCE_MS = 600;

export function useAutosave(source: string, save: (md: string) => Promise<unknown>) {
  const [state, setState] = useState<SaveState>('saved');
  const [savedAt, setSavedAt] = useState<Date | undefined>(undefined);
  const lastSavedRef = useRef<string>(source);
  const timerRef = useRef<number | null>(null);
  const pendingRef = useRef<string>(source);

  const doSave = useCallback(
    async (md: string) => {
      setState('saving');
      try {
        await save(md);
        lastSavedRef.current = md;
        setSavedAt(new Date());
        setState('saved');
      } catch {
        setState('error');
      }
    },
    [save],
  );

  useEffect(() => {
    pendingRef.current = source;
    if (source === lastSavedRef.current) {
      return undefined;
    }
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      void doSave(pendingRef.current);
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [source, doSave]);

  const retry = useCallback(() => {
    void doSave(pendingRef.current);
  }, [doSave]);

  return { state, savedAt, retry };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- useAutosave`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/useAutosave.ts packages/web/src/components/openorg/useAutosave.test.ts
git commit -m "feat(openorg): add useAutosave debounced hook"
```

---

## Task 4.3 — Wire autosave + SaveIndicator into EditorShell

**Files:**
- Modify: `packages/web/src/components/openorg/EditorShell.tsx`
- Modify: `packages/web/src/components/openorg/EditorShell.test.tsx`

EditorShell threads autosave through the guided surface and shows the SaveIndicator above the editor body. The markdown surface keeps its explicit Save button + 'Unsaved' indicator.

- [ ] **Step 1: Write the failing test**

Append to `EditorShell.test.tsx`:

```typescript
import { vi as vi2 } from 'vitest';
// Above tests already import vi; this is a marker — reuse the existing import.

  it('autosaves the guided surface after a debounce window', async () => {
    vi.useFakeTimers();
    const onSave = vi.fn(async () => undefined);
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={onSave}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    expect(onSave).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(700);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).toContain('name: Trussell');
    vi.useRealTimers();
  });

  it('shows the save indicator', () => {
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/saved/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- EditorShell`
Expected: FAIL — autosave wiring + indicator not yet present.

- [ ] **Step 3: Update `EditorShell.tsx`**

```typescript
import { useEffect, useState } from 'react';
import MarkdownEditor from './MarkdownEditor';
import GuidedEditor from './guided/GuidedEditor';
import SurfaceSwitch, { useEditorSurface, type RecordKind } from './SurfaceSwitch';
import SaveIndicator from './SaveIndicator';
import { useAutosave } from './useAutosave';
import type { GuidedSection } from './guided/sections/profile';
import type { PillOption } from './guided/fields/PillPicker';
import type { ValidationFieldError } from '../../api/openorg';

interface EditorShellProps {
  kind: RecordKind;
  initialSource: string;
  sections: GuidedSection[];
  onSave: (markdown: string) => Promise<unknown>;
  vocabs: Record<string, PillOption[]>;
  saving?: boolean;
  validationErrors?: ValidationFieldError[];
  saveLabel?: string;
  startHereId?: string;
}

export default function EditorShell({
  kind,
  initialSource,
  sections,
  onSave,
  vocabs,
  saving = false,
  validationErrors = [],
  saveLabel = 'Save',
  startHereId,
}: EditorShellProps) {
  const [surface, setSurface] = useEditorSurface(kind);
  const [source, setSource] = useState(initialSource);

  useEffect(() => {
    setSource(initialSource);
  }, [initialSource]);

  const autosave = useAutosave(surface === 'guided' ? source : initialSource, onSave);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SaveIndicator state={autosave.state} savedAt={autosave.savedAt} onRetry={autosave.retry} />
        <SurfaceSwitch value={surface} onChange={setSurface} />
      </div>

      {surface === 'guided' ? (
        <GuidedEditor
          source={source}
          sections={sections}
          onChange={setSource}
          vocabs={vocabs}
          startHereId={startHereId}
        />
      ) : (
        <MarkdownEditor
          initialMarkdown={initialSource}
          onSave={async (md) => {
            setSource(md);
            return onSave(md);
          }}
          saving={saving}
          validationErrors={validationErrors}
          saveLabel={saveLabel}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- EditorShell`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/EditorShell.tsx packages/web/src/components/openorg/EditorShell.test.tsx
git commit -m "feat(openorg): wire autosave + SaveIndicator into EditorShell"
```

---

## Task 4.4 — PublishStrip

**Files:**
- Create: `packages/web/src/components/openorg/PublishStrip.tsx`
- Create: `packages/web/src/components/openorg/PublishStrip.test.tsx`
- Modify: `packages/web/src/components/openorg/PublishToggle.tsx` (PublishBadge stays; PublishControls is no longer used by the editors).

Inline confirm strip. On confirmed publish, the strip becomes a one-time celebratory state: gold rule reveal, badge ticks to Published, "Live at … · Share ↗", auto-fade after 8s.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/PublishStrip.test.tsx
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import PublishStrip from './PublishStrip';

describe('PublishStrip (unpublished)', () => {
  it('shows the Publish trigger and a confirm strip on click', () => {
    render(
      <PublishStrip
        published={false}
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
      />,
    );
    expect(screen.getByRole('button', { name: /^publish$/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(screen.getByText(/publish this profile/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /not yet/i })).toBeInTheDocument();
  });

  it('calls onPublish when the confirm button is clicked', () => {
    const onPublish = vi.fn();
    render(
      <PublishStrip
        published={false}
        busy={false}
        onPublish={onPublish}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /^publish$/i }).at(-1)!);
    expect(onPublish).toHaveBeenCalled();
  });
});

describe('PublishStrip (celebration)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('shows the celebration row when justPublishedAt is recent', () => {
    render(
      <PublishStrip
        published
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
        justPublishedAt={new Date()}
      />,
    );
    expect(screen.getByText(/live at/i)).toBeInTheDocument();
    expect(screen.getByText(/share this profile/i)).toBeInTheDocument();
  });

  it('hides the celebration after 8s', () => {
    render(
      <PublishStrip
        published
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
        justPublishedAt={new Date()}
      />,
    );
    act(() => {
      vi.advanceTimersByTime(8_100);
    });
    expect(screen.queryByText(/share this profile/i)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- PublishStrip`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/PublishStrip.tsx
import { useEffect, useState } from 'react';
import { PublishBadge } from './PublishToggle';

interface PublishStripProps {
  published: boolean;
  busy: boolean;
  onPublish: () => void;
  onUnpublish: () => void;
  liveUrl: string;
  /** Set when a publish just succeeded — drives the celebratory state for 8s. */
  justPublishedAt?: Date;
  noun?: string;
}

export default function PublishStrip({
  published,
  busy,
  onPublish,
  onUnpublish,
  liveUrl,
  justPublishedAt,
  noun = 'profile',
}: PublishStripProps) {
  const [confirming, setConfirming] = useState<null | 'publish' | 'unpublish'>(null);
  const [celebrating, setCelebrating] = useState<boolean>(Boolean(justPublishedAt));
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!justPublishedAt) return undefined;
    setCelebrating(true);
    const id = window.setTimeout(() => setCelebrating(false), 8_000);
    return () => window.clearTimeout(id);
  }, [justPublishedAt]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(liveUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_500);
    } catch {
      // Clipboard blocked — leave it; the link is still selectable on the page.
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <PublishBadge published={published} />
        {confirming === null && !published && (
          <button
            type="button"
            onClick={() => setConfirming('publish')}
            disabled={busy}
            className="bg-ink px-4 py-1.5 text-sm font-medium text-paper hover:bg-primary-700 disabled:opacity-40"
          >
            Publish
          </button>
        )}
        {confirming === null && published && !celebrating && (
          <button
            type="button"
            onClick={() => setConfirming('unpublish')}
            disabled={busy}
            className="border border-ink/30 bg-paper px-4 py-1.5 text-sm font-medium text-ink hover:bg-paper-2 disabled:opacity-40"
          >
            Unpublish
          </button>
        )}
      </div>

      {confirming === 'publish' && (
        <div role="region" aria-live="polite" className="border-l-2 border-ink bg-paper-2 px-4 py-3 text-sm">
          <p>
            Publish this {noun} to the federated network? Anyone will be able to see it at{' '}
            <code className="font-mono">{liveUrl}</code>.
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setConfirming(null);
                onPublish();
              }}
              disabled={busy}
              className="bg-ink px-3 py-1 text-xs uppercase tracking-wider text-paper disabled:opacity-40"
            >
              Publish
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="border border-rule px-3 py-1 text-xs uppercase tracking-wider text-muted hover:text-ink"
            >
              Not yet
            </button>
          </div>
        </div>
      )}

      {confirming === 'unpublish' && (
        <div role="region" aria-live="polite" className="border-l-2 border-ink bg-paper-2 px-4 py-3 text-sm">
          <p>Unpublish this {noun}? It will be removed from the federated network.</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setConfirming(null);
                onUnpublish();
              }}
              disabled={busy}
              className="border border-ink/30 bg-paper px-3 py-1 text-xs uppercase tracking-wider text-ink disabled:opacity-40"
            >
              Unpublish
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="border border-rule px-3 py-1 text-xs uppercase tracking-wider text-muted hover:text-ink"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {celebrating && (
        <div className="flex flex-col gap-1">
          <div
            aria-hidden
            className="h-px w-full origin-left bg-amber-500 transition-transform duration-[600ms] ease-out"
            style={{ transform: 'scaleX(1)' }}
          />
          <p className="text-sm text-ink">
            Live at <code className="font-mono">{liveUrl}</code> ·{' '}
            <button
              type="button"
              onClick={handleCopy}
              className="underline decoration-rule underline-offset-2 hover:text-primary-700"
            >
              Share this profile ↗
            </button>
            {copied && <span className="ml-2 text-xs text-emerald-700">Copied</span>}
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- PublishStrip`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/PublishStrip.tsx packages/web/src/components/openorg/PublishStrip.test.tsx
git commit -m "feat(openorg): add PublishStrip with confirm + celebratory state"
```

---

## Task 4.5 — Adopt PublishStrip in EditProfile + wire themes vocab

**Files:**
- Modify: `packages/web/src/pages/openorg/EditProfile.tsx`
- Modify: `packages/web/src/pages/openorg/EditProfile.test.tsx`

Replace `PublishControls` with `PublishStrip`. Source themes vocab from the existing `useThemes()` hook (already in `api/openorg.ts`). Track `justPublishedAt` locally.

- [ ] **Step 1: Update the existing test**

Append a new case in `EditProfile.test.tsx`:

```typescript
  it('renders the inline publish confirm strip on click', async () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(screen.getByText(/publish this profile to the federated network/i)).toBeInTheDocument();
  });
```

Also mock `useThemes` in the existing `vi.mock` block so the call doesn't hit the network:

```typescript
    useThemes: () => ({ isLoading: false, data: [
      { key: 'older_people', label: 'Older people', description: '' },
    ], error: null }),
```

Run: `cd packages/web && npm test -- EditProfile`
Expected: existing tests pass; new test FAILS until the page swaps in PublishStrip.

- [ ] **Step 2: Modify `EditProfile.tsx`**

Replace `PublishControls` use with `PublishStrip`, wire `justPublishedAt`, and wire the themes vocab:

```typescript
import EditorShell from '../../components/openorg/EditorShell';
import PublishStrip from '../../components/openorg/PublishStrip';
import { PROFILE_SECTIONS } from '../../components/openorg/guided/sections/profile';
import { useThemes } from '../../api/openorg';
import { useState } from 'react';
```

In the component body:

```typescript
  const themes = useThemes();
  const [justPublishedAt, setJustPublishedAt] = useState<Date | undefined>();

  const liveUrl = `https://openorg.good-ship.co.uk/openorg/${orgId}`;

  const handlePublish = async () => {
    setPublishError(null);
    try {
      await publish.mutateAsync();
      setJustPublishedAt(new Date());
    } catch (err) {
      if (err instanceof OpenOrgPublishError) {
        setPublishError(err.detail);
      } else {
        throw err;
      }
    }
  };
```

Replace the `<PublishControls …/>` block with `<PublishStrip published={published} busy={mutating} onPublish={handlePublish} onUnpublish={handleUnpublish} liveUrl={liveUrl} justPublishedAt={justPublishedAt} />` and remove the `<PublishBadge>` next to the org id (PublishStrip renders its own badge).

Replace `vocabs={{}}` on `<EditorShell …/>` with:

```typescript
          vocabs={{ themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })) }}
```

- [ ] **Step 3: Run all editor tests**

Run: `cd packages/web && npm test -- EditProfile`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/web/src/pages/openorg/EditProfile.tsx packages/web/src/pages/openorg/EditProfile.test.tsx
git commit -m "feat(openorg): swap PublishControls for PublishStrip in EditProfile"
```

---

## Task 4.6 — Wrap remaining editors in EditorShell + PublishStrip

**Files:**
- Modify: `packages/web/src/pages/openorg/EditStrategy.tsx`
- Modify: `packages/web/src/pages/openorg/EditStrategy.test.tsx`
- Modify: `packages/web/src/pages/openorg/EditIdea.tsx`
- Modify: `packages/web/src/pages/openorg/EditIdea.test.tsx`
- Modify: `packages/web/src/pages/openorg/NewRecord.tsx`
- Modify: `packages/web/src/pages/openorg/NewRecord.test.tsx`

Apply the same pattern as EditProfile to each:

1. Import `EditorShell`, `PublishStrip`, the matching `*_SECTIONS`, and `useThemes`.
2. Replace `<MarkdownEditor … />` with `<EditorShell kind="strategy" sections={STRATEGY_SECTIONS} …/>` (or `idea`).
3. Replace `<PublishControls …/>` with `<PublishStrip …/>` for the two record editors.
4. `NewRecord` doesn't have publish controls (it redirects after save) — only the editor swap is needed.

For each, update the test file's `vi.mock` block to add `useThemes` like in 4.5.

- [ ] **Step 1: Wire EditStrategy**

Test (append in `EditStrategy.test.tsx`):

```typescript
  it('renders the guided sidebar with strategy sections', () => {
    mockStrategyData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\nid: my-strategy\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1', 'my-strategy');
    expect(screen.getByRole('button', { name: /^priorities/i })).toBeInTheDocument();
  });
```

Implementation: in `EditStrategy.tsx`, swap as above:

```typescript
import EditorShell from '../../components/openorg/EditorShell';
import PublishStrip from '../../components/openorg/PublishStrip';
import { STRATEGY_SECTIONS } from '../../components/openorg/guided/sections/strategy';
import { useThemes } from '../../api/openorg';

// ...

  const themes = useThemes();
  const [justPublishedAt, setJustPublishedAt] = useState<Date | undefined>();
  const liveUrl = `https://openorg.good-ship.co.uk/openorg/${orgId}/strategies/${slug}`;
```

Replace editor block:

```typescript
        <EditorShell
          kind="strategy"
          initialSource={strategy.data?.markdown ?? ''}
          sections={STRATEGY_SECTIONS}
          onSave={handleSave}
          vocabs={{ themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })) }}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save strategy"
        />
```

Replace publish controls:

```typescript
        <PublishStrip
          published={Boolean(strategy.data?.published)}
          busy={publish.isPending || unpublish.isPending}
          onPublish={async () => {
            try {
              await publish.mutateAsync();
              setJustPublishedAt(new Date());
            } catch (e) { if (e instanceof OpenOrgPublishError) setPublishError(e.detail); else throw e; }
          }}
          onUnpublish={handleUnpublish}
          liveUrl={liveUrl}
          justPublishedAt={justPublishedAt}
          noun="strategy"
        />
```

Run: `cd packages/web && npm test -- EditStrategy`
Expected: PASS.

```bash
git add packages/web/src/pages/openorg/EditStrategy.tsx packages/web/src/pages/openorg/EditStrategy.test.tsx
git commit -m "feat(openorg): wrap EditStrategy in EditorShell with PublishStrip"
```

- [ ] **Step 2: Wire EditIdea**

Same pattern with `IDEA_SECTIONS`, `kind="idea"`, `noun="idea"`, save label "Save idea", live URL `/openorg/${orgId}/ideas/${slug}`.

Test addition mirrors EditStrategy's. Add `useThemes` mock and an assertion for an idea section button.

```bash
git add packages/web/src/pages/openorg/EditIdea.tsx packages/web/src/pages/openorg/EditIdea.test.tsx
git commit -m "feat(openorg): wrap EditIdea in EditorShell with PublishStrip"
```

- [ ] **Step 3: Wire NewRecord**

For NewRecord, `kind` is the prop already passed (`strategy` | `idea`) — pass through directly. Don't add publish — NewRecord redirects to the proper edit page on save.

```typescript
import EditorShell from '../../components/openorg/EditorShell';
import { STRATEGY_SECTIONS } from '../../components/openorg/guided/sections/strategy';
import { IDEA_SECTIONS } from '../../components/openorg/guided/sections/idea';
import { useThemes } from '../../api/openorg';

// ...
  const themes = useThemes();
  const sections = kind === 'strategy' ? STRATEGY_SECTIONS : IDEA_SECTIONS;

// Replace MarkdownEditor with:
        <EditorShell
          kind={kind}
          initialSource={template}
          sections={sections}
          onSave={handleSave}
          vocabs={{ themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })) }}
          saving={saving}
          validationErrors={validationErrors}
          saveLabel={`Save ${noun}`}
        />
```

Test addition: assert the sidebar button for the relevant kind appears (existing tests cover the rest).

Run: `cd packages/web && npm test -- NewRecord`
Expected: PASS.

```bash
git add packages/web/src/pages/openorg/NewRecord.tsx packages/web/src/pages/openorg/NewRecord.test.tsx
git commit -m "feat(openorg): wrap NewRecord in EditorShell"
```

## Task 4.7 — Static vocabularies for non-theme pills

**Files:**
- Create: `packages/web/src/components/openorg/guided/vocabs.ts`
- Create: `packages/web/src/components/openorg/guided/vocabs.test.ts`
- Modify: EditProfile / EditStrategy / EditIdea / NewRecord (merge static vocabs into the `vocabs` prop)

`useThemes()` covers `themes`. The other pill vocabs in the section specs (`beneficiaries`, `status`, `access_level`, `horizon`, `connections`, `strategy_status`, `idea_status`) aren't backed by API hooks. Hard-code small controlled vocabs here so single-select pills (status, horizon, access_level) actually have options to choose from.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/guided/vocabs.test.ts
import { describe, expect, it } from 'vitest';
import { STATIC_VOCABS } from './vocabs';

describe('STATIC_VOCABS', () => {
  it('has the strategy_status vocab', () => {
    expect(STATIC_VOCABS.strategy_status.length).toBeGreaterThan(0);
  });
  it('has the horizon vocab', () => {
    expect(STATIC_VOCABS.horizon.map((o) => o.key)).toContain('short');
  });
  it('has the access_level vocab', () => {
    expect(STATIC_VOCABS.access_level.map((o) => o.key)).toEqual(
      expect.arrayContaining(['public', 'authenticated', 'private']),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- vocabs`
Expected: FAIL.

- [ ] **Step 3: Write `vocabs.ts`**

```typescript
// packages/web/src/components/openorg/guided/vocabs.ts
import type { PillOption } from './fields/PillPicker';

export const STATIC_VOCABS: Record<string, PillOption[]> = {
  strategy_status: [
    { key: 'draft', label: 'Draft' },
    { key: 'live', label: 'Live' },
    { key: 'completed', label: 'Completed' },
    { key: 'paused', label: 'Paused' },
  ],
  idea_status: [
    { key: 'seed', label: 'Seed' },
    { key: 'developing', label: 'Developing' },
    { key: 'piloting', label: 'Piloting' },
    { key: 'scaling', label: 'Scaling' },
    { key: 'paused', label: 'Paused' },
  ],
  access_level: [
    { key: 'public', label: 'Public' },
    { key: 'authenticated', label: 'Authenticated' },
    { key: 'private', label: 'Private' },
  ],
  horizon: [
    { key: 'short', label: 'Short (under 1 year)' },
    { key: 'medium', label: 'Medium (1-3 years)' },
    { key: 'long', label: 'Long (3+ years)' },
  ],
  beneficiaries: [
    { key: 'older_people', label: 'Older people' },
    { key: 'children', label: 'Children & families' },
    { key: 'young_people', label: 'Young people' },
    { key: 'disabled_people', label: 'Disabled people' },
    { key: 'homelessness', label: 'People experiencing homelessness' },
    { key: 'refugees', label: 'Refugees & people seeking asylum' },
    { key: 'low_income', label: 'People on low incomes' },
    { key: 'lgbtq', label: 'LGBTQ+ people' },
  ],
  connections: [
    { key: 'seeking_partners', label: 'Seeking partners' },
    { key: 'seeking_funders', label: 'Seeking funders' },
    { key: 'sharing_evidence', label: 'Sharing evidence' },
    { key: 'open_to_replication', label: 'Open to replication' },
  ],
};
```

- [ ] **Step 4: Merge into editor pages**

In each of `EditProfile.tsx`, `EditStrategy.tsx`, `EditIdea.tsx`, `NewRecord.tsx`, change the `vocabs={…}` prop to merge in the static set:

```typescript
import { STATIC_VOCABS } from '../../components/openorg/guided/vocabs';
// ...
          vocabs={{
            ...STATIC_VOCABS,
            themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })),
          }}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd packages/web && npm test -- vocabs`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/web/src/components/openorg/guided/vocabs.ts packages/web/src/components/openorg/guided/vocabs.test.ts packages/web/src/pages/openorg/
git commit -m "feat(openorg): add static vocabs for non-theme pill fields"
```

---

- [ ] **Step 4: PR gate**

```bash
cd packages/web && npm run build && npm run lint && npm test
```

Expected: all green. Open PR 4 (`editor-polish-pr4-publish`).

---

# PR 5 — Backend generation status + Generate live flow

Goal: add five nullable columns to `OrgProfile` for fine-grained generation state; have the Celery task write stage transitions; expose two new GET routes (`/lookup/{number}`, `/generate/{org_id}/status`); display live progress on Generate.tsx.

Pre-flight: branch `editor-polish-pr5-generate` off `master` (after PR 4 lands).

## Task 5.1 — Alembic migration for generation status columns

**Files:**
- Create: `packages/api/alembic/versions/d3e4f5a6b7c8_open_org_generation_status_columns.py`

The current migration head is `c2d3e4f5a6b7` (open_org_claim_flow). This new revision is additive — five nullable columns. Existing rows survive untouched (NULL is the resting state for already-`ready` profiles).

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/test_open_org_generation_status_migration.py
"""Smoke test: the new migration's columns are reachable from the ORM model."""

from __future__ import annotations


def test_orgprofile_has_generation_stage_columns():
    from llmstxt_api.open_org_models import OrgProfile

    cols = {col.name for col in OrgProfile.__table__.columns}
    assert {
        "generation_stage",
        "generation_message",
        "generation_payload",
        "generation_started_at",
        "generation_finished_at",
    }.issubset(cols)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_open_org_generation_status_migration.py -v`
Expected: FAIL — columns not yet on the model.

- [ ] **Step 3: Write the migration**

```python
# packages/api/alembic/versions/d3e4f5a6b7c8_open_org_generation_status_columns.py
"""Open Org: fine-grained generation status columns on org_profiles.

Adds five nullable columns powering the live-progress display on the Generate
page. The existing ``generation_status`` (pending/generating/ready/failed)
stays as the headline state; the new columns carry the human-readable stage
message, a small payload, and start/finish timestamps.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-19 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "org_profiles",
        sa.Column("generation_stage", sa.String(40), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_message", sa.String(200), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_payload", JSONB(), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_finished_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("org_profiles", "generation_finished_at")
    op.drop_column("org_profiles", "generation_started_at")
    op.drop_column("org_profiles", "generation_payload")
    op.drop_column("org_profiles", "generation_message")
    op.drop_column("org_profiles", "generation_stage")
```

- [ ] **Step 4: Add columns to the ORM model**

Edit `packages/api/src/llmstxt_api/open_org_models.py` — insert after the existing `generation_error` line (around line 58):

```python
    # Fine-grained generation progress, populated only during the first
    # 30-90s of an org's life. Cleared on completion isn't required —
    # the values stay as a useful diagnostic record.
    generation_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    generation_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generation_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generation_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 5: Run the test and apply the migration**

Run: `cd packages/api && pytest tests/test_open_org_generation_status_migration.py -v && alembic upgrade head`
Expected: test PASS; alembic prints `Running upgrade c2d3e4f5a6b7 -> d3e4f5a6b7c8`.

- [ ] **Step 6: Commit**

```bash
git add packages/api/alembic/versions/d3e4f5a6b7c8_open_org_generation_status_columns.py packages/api/src/llmstxt_api/open_org_models.py packages/api/tests/test_open_org_generation_status_migration.py
git commit -m "feat(openorg): add fine-grained generation status columns"
```

---

## Task 5.2 — Celery task writes stage transitions

**Files:**
- Modify: `packages/api/src/llmstxt_api/tasks/open_org_generate.py`
- Modify: `packages/api/tests/test_open_org_generate_task.py`

Wrap the existing single-shot generator call so the task writes stage transitions: `pulling_cc` → `crawling` → `extracting` → `drafting` → `finalising` → `done` (or `error`). For Phase 1 we instrument at the task boundary (before/after the generator call). Finer-grained stages can come later from generator callbacks.

The task already sets `generation_status="generating"` at the top; we now also write `generation_stage` + `generation_message` + `generation_started_at` then later `generation_finished_at` + `generation_payload`.

- [ ] **Step 1: Write the failing test**

Append to `packages/api/tests/test_open_org_generate_task.py`:

```python
# Top of file imports already include mock + pytest etc.

@pytest.mark.asyncio
async def test_run_generation_writes_stage_transitions_to_row():
    from datetime import datetime
    from llmstxt_api.tasks.open_org_generate import _run_generation
    from llmstxt_core.open_org.generator import GenerationResult

    row = mock.MagicMock()
    row.generation_status = "pending"
    row.generation_stage = None
    row.generation_message = None
    row.generation_started_at = None
    row.generation_finished_at = None
    row.generation_payload = None

    session = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    session.execute = mock.AsyncMock(return_value=fetched)
    session.commit = mock.AsyncMock()

    class _SessionMaker:
        def __call__(self):
            class _CM:
                async def __aenter__(self_inner):
                    return session
                async def __aexit__(self_inner, *a):
                    return False
            return _CM()

    generator = mock.AsyncMock(
        return_value=GenerationResult(
            markdown="---\n---\n",
            json_payload={"identity": {"name": "X"}, "mission": {"themes": ["x"], "programmes": []}},
            org_id="GB-CHC-1",
            total_usage=mock.MagicMock(input_tokens=0, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0, model="claude-x"),
        )
    )
    send_email = mock.AsyncMock()

    import uuid
    await _run_generation(
        profile_id=uuid.uuid4(),
        charity_number="1234567",
        owner_email="o@example.com",
        session_maker=_SessionMaker(),
        generator=generator,
        send_claim_email=send_email,
    )

    # The task wrote at least these stages in order.
    stage_history = [
        call_args.args[0] if call_args.args else None
        for call_args in session.commit.await_args_list
    ]
    # We can't directly inspect stage_history from commit calls; instead inspect
    # the row's last-written values.
    assert row.generation_status == "ready"
    assert row.generation_stage == "done"
    assert row.generation_payload is not None
    assert row.generation_started_at is not None
    assert row.generation_finished_at is not None
    assert isinstance(row.generation_started_at, datetime)


@pytest.mark.asyncio
async def test_run_generation_writes_error_stage_on_failure():
    from llmstxt_api.tasks.open_org_generate import _run_generation

    row = mock.MagicMock()
    row.generation_status = "pending"

    session = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    session.execute = mock.AsyncMock(return_value=fetched)
    session.commit = mock.AsyncMock()

    class _SessionMaker:
        def __call__(self):
            class _CM:
                async def __aenter__(self_inner):
                    return session
                async def __aexit__(self_inner, *a):
                    return False
            return _CM()

    async def boom(**kwargs):
        raise RuntimeError("kaboom")

    import uuid
    await _run_generation(
        profile_id=uuid.uuid4(),
        charity_number="1234567",
        owner_email="o@example.com",
        session_maker=_SessionMaker(),
        generator=boom,
        send_claim_email=mock.AsyncMock(),
    )

    assert row.generation_status == "failed"
    assert row.generation_stage == "error"
    assert row.generation_finished_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_open_org_generate_task.py::test_run_generation_writes_stage_transitions_to_row -v`
Expected: FAIL — task doesn't set new columns yet.

- [ ] **Step 3: Modify `_run_generation` in `packages/api/src/llmstxt_api/tasks/open_org_generate.py`**

Replace the body of `_run_generation` with:

```python
async def _run_generation(
    *,
    profile_id: uuid.UUID,
    charity_number: str,
    owner_email: str,
    session_maker: Any,
    generator: GeneratorFn,
    send_claim_email: SendEmailFn,
    anthropic_client: CachedAnthropic | None = None,
    cc_api_key: str | None = None,
) -> None:
    from datetime import datetime as _dt

    async with session_maker() as session:
        row = await _fetch_row(session, profile_id)
        if row is None:
            log.error("OrgProfile row %s not found for generation", profile_id)
            return

        row.generation_status = "generating"
        row.generation_error = None
        row.generation_stage = "extracting"
        row.generation_message = "Reading what we found…"
        row.generation_started_at = _dt.utcnow()
        row.generation_finished_at = None
        row.generation_payload = None
        await session.commit()

        try:
            result = await generator(
                charity_number=charity_number,
                anthropic_client=anthropic_client,
                cc_api_key=cc_api_key,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)[:_ERROR_MESSAGE_MAX] or exc.__class__.__name__
            row.generation_status = "failed"
            row.generation_error = message
            row.generation_stage = "error"
            row.generation_message = "Couldn't finish — see error below."
            row.generation_finished_at = _dt.utcnow()
            await session.commit()
            log.warning(
                "open_org generation failed for %s: %s", charity_number, message
            )
            return

        row.markdown_source = result.markdown
        row.profile_json = result.json_payload
        row.generation_status = "ready"
        row.generation_error = None
        row.generation_stage = "done"
        row.generation_message = "Draft ready."
        row.generation_finished_at = _dt.utcnow()
        row.generation_payload = _summary_payload(result.json_payload)

        llm_usage_service.log_usage(
            session,
            feature="profile_generator",
            usage=result.total_usage,
            org_id=result.org_id,
        )
        await session.commit()

        await send_claim_email(
            db=session, email=owner_email, org_id=result.org_id
        )


def _summary_payload(profile_json: dict | None) -> dict:
    """Compact preview of what the generator found.

    Drives the "14 programmes mentioned, 4 themes…" line on the Generate page's
    success state. Pure derivation from the JSON — safe to recompute.
    """
    if not profile_json:
        return {}
    mission = profile_json.get("mission") or {}
    return {
        "themes_count": len(mission.get("themes") or []),
        "programmes_count": len(mission.get("programmes") or []),
        "has_summary": bool((mission.get("summary") or "").strip()),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/test_open_org_generate_task.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/tasks/open_org_generate.py packages/api/tests/test_open_org_generate_task.py
git commit -m "feat(openorg): write generation stage transitions to OrgProfile"
```

---

## Task 5.3 — `GET /api/open-org/generate/{org_id}/status` route

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_generate.py`
- Create: `packages/api/tests/test_open_org_generate_status_route.py`

Adds the polling endpoint. Unauthenticated — the Generate page polls it during the wait window, before the user has any session.

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/test_open_org_generate_status_route.py
"""Tests for GET /api/open-org/generate/{org_id}/status."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


@pytest.mark.asyncio
async def test_status_returns_current_stage_for_known_org():
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import generate_status

    row = mock.MagicMock(spec=OrgProfile)
    row.org_id = "GB-CHC-1234567"
    row.generation_status = "generating"
    row.generation_stage = "drafting"
    row.generation_message = "Drafting your profile…"
    row.generation_payload = None
    row.generation_started_at = datetime.utcnow() - timedelta(seconds=12)
    row.generation_finished_at = None

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    db.execute = mock.AsyncMock(return_value=fetched)

    response = await generate_status(org_id="GB-CHC-1234567", db=db)

    assert response.status == "generating"
    assert response.stage == "drafting"
    assert response.message == "Drafting your profile…"
    assert response.elapsed_ms >= 12_000


@pytest.mark.asyncio
async def test_status_404_on_unknown_org():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import generate_status

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = None
    db.execute = mock.AsyncMock(return_value=fetched)

    with pytest.raises(HTTPException) as exc:
        await generate_status(org_id="GB-CHC-9999999", db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_status_returns_payload_on_done():
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import generate_status

    row = mock.MagicMock(spec=OrgProfile)
    row.org_id = "GB-CHC-1"
    row.generation_status = "ready"
    row.generation_stage = "done"
    row.generation_message = "Draft ready."
    row.generation_payload = {"themes_count": 4, "programmes_count": 14, "has_summary": True}
    row.generation_started_at = datetime.utcnow() - timedelta(seconds=47)
    row.generation_finished_at = datetime.utcnow()

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    db.execute = mock.AsyncMock(return_value=fetched)

    response = await generate_status(org_id="GB-CHC-1", db=db)

    assert response.status == "ready"
    assert response.payload == {"themes_count": 4, "programmes_count": 14, "has_summary": True}
    assert response.elapsed_ms >= 47_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_open_org_generate_status_route.py -v`
Expected: FAIL — `generate_status` not defined.

- [ ] **Step 3: Append the route in `open_org_generate.py`**

After the existing `generate_profile` route:

```python
class GenerateStatusResponse(BaseModel):
    org_id: str
    status: str
    stage: str | None
    message: str | None
    payload: dict | None
    elapsed_ms: int


@router.get(
    "/generate/{org_id}/status",
    response_model=GenerateStatusResponse,
)
async def generate_status(
    org_id: str,
    db: AsyncSession = Depends(get_db),
) -> GenerateStatusResponse:
    """Live polling endpoint for the Generate.tsx live progress display.

    Unauthenticated — see spec section 1. The page polls every 2s during
    the 30-90s generation window.
    """
    result = await db.execute(select(OrgProfile).where(OrgProfile.org_id == org_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="org not found")

    started = row.generation_started_at
    finished = row.generation_finished_at
    from datetime import datetime as _dt

    if finished is not None and started is not None:
        elapsed = int((finished - started).total_seconds() * 1000)
    elif started is not None:
        elapsed = int((_dt.utcnow() - started).total_seconds() * 1000)
    else:
        elapsed = 0

    return GenerateStatusResponse(
        org_id=row.org_id,
        status=row.generation_status,
        stage=row.generation_stage,
        message=row.generation_message,
        payload=row.generation_payload,
        elapsed_ms=elapsed,
    )
```

Also add `GenerateStatusResponse` and `generate_status` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/test_open_org_generate_status_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/open_org_generate.py packages/api/tests/test_open_org_generate_status_route.py
git commit -m "feat(openorg): add GET /generate/{org_id}/status route"
```

---

## Task 5.4 — `GET /api/open-org/lookup/{number}` route

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_generate.py`
- Create: `packages/api/tests/test_open_org_lookup_route.py`

Charity Commission name+address lookup, used by Generate.tsx for the inline "Match: …" line. Reuses `llmstxt_core.enrichers.charity_commission.fetch_charity_data`.

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/test_open_org_lookup_route.py
"""Tests for GET /api/open-org/lookup/{number}."""

from __future__ import annotations

from unittest import mock

import pytest


@pytest.mark.asyncio
async def test_lookup_returns_name_and_address():
    from llmstxt_api.routes.open_org_generate import lookup_charity
    from llmstxt_core.enrichers.charity_commission import CharityData

    cd = CharityData(
        name="The Trussell Trust",
        number="1110522",
        status="Registered",
        date_registered="2005-04-19",
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects=None,
        activities=None,
        trustees=[],
        contact={"address": {"line1": "Unit 9", "line2": "Ashfield Trading Estate", "postcode": "SP2 7HL"}},
    )
    with mock.patch(
        "llmstxt_api.routes.open_org_generate.fetch_charity_data",
        new=mock.AsyncMock(return_value=cd),
    ):
        response = await lookup_charity(number="1110522")

    assert response.name == "The Trussell Trust"
    assert response.registered_address is not None
    assert "Ashfield" in response.registered_address


@pytest.mark.asyncio
async def test_lookup_404_when_not_found():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import lookup_charity

    with mock.patch(
        "llmstxt_api.routes.open_org_generate.fetch_charity_data",
        new=mock.AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc:
            await lookup_charity(number="9999999")
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_lookup_rejects_invalid_format():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import lookup_charity

    with pytest.raises(HTTPException) as exc:
        await lookup_charity(number="abc")
    assert exc.value.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/test_open_org_lookup_route.py -v`
Expected: FAIL.

- [ ] **Step 3: Append the lookup route**

Add to the imports at the top of `open_org_generate.py`:

```python
import re as _re
from llmstxt_api.config import settings
from llmstxt_core.enrichers.charity_commission import fetch_charity_data
```

Add the route + schema:

```python
_NUMBER_RE = _re.compile(r"^[0-9]{6,8}$")


class LookupResponse(BaseModel):
    number: str
    name: str
    registered_address: str | None


def _format_address(contact: dict | None) -> str | None:
    if not contact:
        return None
    addr = contact.get("address") or {}
    parts = [addr.get(k) for k in ("line1", "line2", "line3", "city", "postcode")]
    cleaned = [p for p in parts if p]
    return ", ".join(cleaned) if cleaned else None


@router.get(
    "/lookup/{number}",
    response_model=LookupResponse,
)
async def lookup_charity(number: str) -> LookupResponse:
    """Look up a UK charity by registration number.

    Powers the inline "Match: <name>" reassurance line on the Generate page.
    Cached weakly upstream by the CC enricher; this endpoint adds no extra
    caching beyond what the enricher already provides.
    """
    if not _NUMBER_RE.match(number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="number must be 6-8 digits",
        )
    cd = await fetch_charity_data(number, api_key=settings.charity_commission_api_key)
    if cd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="charity not found",
        )
    return LookupResponse(
        number=cd.number,
        name=cd.name,
        registered_address=_format_address(cd.contact),
    )
```

Append `LookupResponse`, `lookup_charity` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/test_open_org_lookup_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/open_org_generate.py packages/api/tests/test_open_org_lookup_route.py
git commit -m "feat(openorg): add GET /lookup/{number} charity name lookup"
```

---

## Task 5.5 — API client: `lookupCharity` + `getGenerateStatus`

**Files:**
- Modify: `packages/web/src/api/openorg.ts`

Add typed client wrappers and a TanStack `useQuery` for the status poll.

- [ ] **Step 1: Append types and functions to `openorg.ts`**

```typescript
export interface LookupResponse {
  number: string;
  name: string;
  registered_address: string | null;
}

export async function lookupCharity(number: string): Promise<LookupResponse> {
  const { data } = await api.get(`/api/open-org/lookup/${number}`);
  return data;
}

export interface GenerateStatusResponse {
  org_id: string;
  status: 'pending' | 'generating' | 'ready' | 'failed';
  stage: string | null;
  message: string | null;
  payload: { themes_count?: number; programmes_count?: number; has_summary?: boolean } | null;
  elapsed_ms: number;
}

export async function getGenerateStatus(orgId: string): Promise<GenerateStatusResponse> {
  const { data } = await api.get(`/api/open-org/generate/${orgId}/status`);
  return data;
}

export function useGenerateStatus(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['openorg', 'generate-status', orgId],
    queryFn: () => getGenerateStatus(orgId),
    enabled: enabled && Boolean(orgId),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return 2_000;
      if (data.status === 'ready' || data.status === 'failed') return false;
      return 2_000;
    },
    retry: false,
  });
}
```

- [ ] **Step 2: Type-check**

Run: `cd packages/web && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add packages/web/src/api/openorg.ts
git commit -m "feat(openorg): add lookupCharity and useGenerateStatus client hooks"
```

---

## Task 5.6 — GenerateLiveStatus component

**Files:**
- Create: `packages/web/src/components/openorg/GenerateLiveStatus.tsx`
- Create: `packages/web/src/components/openorg/GenerateLiveStatus.test.tsx`

Live-progress panel: shows the current stage message, fades each new stage in, switches to the "still working in the background" line after 90s.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/GenerateLiveStatus.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import GenerateLiveStatus from './GenerateLiveStatus';

describe('GenerateLiveStatus', () => {
  it('shows the current stage message', () => {
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'generating',
          stage: 'drafting',
          message: 'Drafting your profile…',
          payload: null,
          elapsed_ms: 12_000,
        }}
        onTimeout={vi.fn()}
      />,
    );
    expect(screen.getByText('Drafting your profile…')).toBeInTheDocument();
  });

  it('shows the done summary when status is ready', () => {
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'ready',
          stage: 'done',
          message: 'Draft ready.',
          payload: { themes_count: 4, programmes_count: 14, has_summary: true },
          elapsed_ms: 47_000,
        }}
        onTimeout={vi.fn()}
      />,
    );
    expect(screen.getByText(/draft ready/i)).toBeInTheDocument();
    expect(screen.getByText(/took 47 seconds/i)).toBeInTheDocument();
    expect(screen.getByText(/14 programmes/i)).toBeInTheDocument();
  });

  it('calls onTimeout when elapsed > 90s and status still generating', () => {
    const onTimeout = vi.fn();
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'generating',
          stage: 'drafting',
          message: 'Drafting…',
          payload: null,
          elapsed_ms: 91_000,
        }}
        onTimeout={onTimeout}
      />,
    );
    expect(onTimeout).toHaveBeenCalled();
    expect(screen.getByText(/still working in the background/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- GenerateLiveStatus`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/GenerateLiveStatus.tsx
import { useEffect } from 'react';
import type { GenerateStatusResponse } from '../../api/openorg';

interface GenerateLiveStatusProps {
  status: GenerateStatusResponse;
  onTimeout: () => void;
}

const FALLBACK_THRESHOLD_MS = 90_000;

function donePreview(payload: GenerateStatusResponse['payload']): string {
  if (!payload) return '';
  const parts: string[] = [];
  if (payload.programmes_count) parts.push(`${payload.programmes_count} programmes`);
  if (payload.themes_count) parts.push(`${payload.themes_count} themes`);
  if (payload.has_summary) parts.push('a strong mission statement');
  if (parts.length === 0) return '';
  return parts.join(', ');
}

export default function GenerateLiveStatus({ status, onTimeout }: GenerateLiveStatusProps) {
  const timedOut = status.status === 'generating' && status.elapsed_ms > FALLBACK_THRESHOLD_MS;

  useEffect(() => {
    if (timedOut) onTimeout();
  }, [timedOut, onTimeout]);

  if (status.status === 'failed') {
    return (
      <div className="border-l-2 border-red-700/40 bg-red-50/40 px-4 py-3 text-sm text-red-900">
        Couldn't finish — please try again, or email us if it keeps failing.
      </div>
    );
  }

  if (status.status === 'ready') {
    const took = Math.max(1, Math.round(status.elapsed_ms / 1000));
    const preview = donePreview(status.payload);
    return (
      <div className="border-l-2 border-emerald-700/40 bg-emerald-50/40 px-4 py-3">
        <div className="kicker text-emerald-900">✓ Draft ready</div>
        <p className="mt-1 text-sm text-ink">
          Took {took} seconds. {preview && <>{preview} found.</>}
        </p>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="border-l-2 border-rule bg-paper-2 px-4 py-3 text-sm text-ink">
        Still working in the background — we'll email you when it's ready, feel
        free to close this tab.
      </div>
    );
  }

  return (
    <div className="border-l-2 border-rule bg-paper-2 px-4 py-3 text-sm text-ink transition-opacity duration-200">
      {status.message ?? 'Working…'}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- GenerateLiveStatus`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/GenerateLiveStatus.tsx packages/web/src/components/openorg/GenerateLiveStatus.test.tsx
git commit -m "feat(openorg): add GenerateLiveStatus component"
```

---

## Task 5.7 — Wire Generate.tsx to lookup + live status

**Files:**
- Modify: `packages/web/src/pages/openorg/Generate.tsx`
- Modify: `packages/web/src/pages/openorg/Generate.test.tsx`

Two changes:

1. Inline charity-number recognition — debounce 400ms, call `lookupCharity`. Show `Match: <name>` line on success; nothing on failure (don't pre-empt the submit error).
2. Replace the static "Check your inbox" screen with `GenerateLiveStatus` polling `useGenerateStatus(orgId, enabled=submitted)`.

- [ ] **Step 1: Update the existing test**

Open `Generate.test.tsx` and append:

```typescript
  it('shows the live status panel after a successful submit', async () => {
    // existing test setup already mocks generateProfile; add useGenerateStatus mock.
    // (Adjust the existing vi.mock block to also include:)
    //   useGenerateStatus: () => ({ data: { status: 'generating', stage: 'drafting',
    //     message: 'Drafting your profile…', payload: null, elapsed_ms: 5000, org_id: 'GB-CHC-1' } })
    // Then trigger submit and assert:
    // expect(screen.getByText(/drafting your profile/i)).toBeInTheDocument();
  });
```

Concretely, update the existing `vi.mock('../../api/openorg', …)` to add `useGenerateStatus`. Then trigger the submit and assert the stage message renders.

Run: `cd packages/web && npm test -- Generate.test`
Expected: existing tests still pass; new test FAILS.

- [ ] **Step 2: Modify `Generate.tsx`**

Add imports:

```typescript
import { useEffect, useRef } from 'react';
import { generateProfile, lookupCharity, useGenerateStatus, OpenOrgGenerateError } from '../../api/openorg';
import GenerateLiveStatus from '../../components/openorg/GenerateLiveStatus';
```

Add lookup state inside the component, above the submit handler:

```typescript
  const [lookupName, setLookupName] = useState<string | null>(null);
  const lookupTimer = useRef<number | null>(null);

  useEffect(() => {
    const value = charityNumber.trim();
    if (lookupTimer.current !== null) {
      window.clearTimeout(lookupTimer.current);
      lookupTimer.current = null;
    }
    if (!CHARITY_NUMBER_RE.test(value)) {
      setLookupName(null);
      return undefined;
    }
    lookupTimer.current = window.setTimeout(() => {
      lookupCharity(value)
        .then((r) => setLookupName(r.name))
        .catch(() => setLookupName(null));
    }, 400);
    return () => {
      if (lookupTimer.current !== null) {
        window.clearTimeout(lookupTimer.current);
        lookupTimer.current = null;
      }
    };
  }, [charityNumber]);
```

Render the match line under the charity-number input:

```typescript
            {lookupName && (
              <span className="mt-1 text-xs text-emerald-700">Match: {lookupName}</span>
            )}
```

Add the trust line above the submit button:

```typescript
          <p className="text-xs italic text-muted">
            We won't publish anything without your say-so.
          </p>
```

Replace the `if (submitted) {…}` static screen with the live-status hookup:

```typescript
  const statusQuery = useGenerateStatus(submitted?.orgId ?? '', Boolean(submitted));

  if (submitted) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <div className="kicker num">Generation kicked off</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Drafting your profile
          </h1>
          <p className="mt-4 max-w-prose text-sm text-muted">
            We're emailing <strong>{submitted.email}</strong> a one-time link
            you can use to claim and edit the draft.
          </p>
          <div className="mt-6">
            {statusQuery.data && (
              <GenerateLiveStatus status={statusQuery.data} onTimeout={() => undefined} />
            )}
          </div>
        </div>
      </div>
    );
  }
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd packages/web && npm test -- Generate`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/web/src/pages/openorg/Generate.tsx packages/web/src/pages/openorg/Generate.test.tsx
git commit -m "feat(openorg): live progress + charity-name preview on Generate"
```

---

## Task 5.8 — PR gate

- [ ] **Step 1: Full backend + frontend test sweep**

Run, in two terminals or sequentially:

```bash
cd packages/api && pytest tests/
cd packages/web && npm run build && npm run lint && npm test
```

Expected: all green. Open PR 5 (`editor-polish-pr5-generate`).

---

# PR 6 — WelcomeStrip + microcopy sweep

Goal: surface `claim_org_id` on the `AuthResponse`, redirect post-claim to the editor, set a one-time welcome-strip flag, render the WelcomeStrip in EditorShell, and extract the user-facing strings into a single `microcopy.ts` module.

Pre-flight: branch `editor-polish-pr6-welcome` off `master` (after PR 5 lands).

## Task 6.1 — Surface `claim_org_id` on the verify response

**Files:**
- Modify: `packages/api/src/llmstxt_api/schemas.py`
- Modify: `packages/api/src/llmstxt_api/routes/auth.py`
- Modify: `packages/api/tests/test_open_org_claim_flow.py`

`AuthResponse` gains a nullable `claim_org_id`; the verify endpoint returns the magic-link token's `org_id` when present.

- [ ] **Step 1: Add a failing test**

Append to `test_open_org_claim_flow.py`:

```python
@pytest.mark.asyncio
async def test_verify_returns_claim_org_id_when_token_carries_one(async_client, db_session):
    # Existing claim_flow tests set up an org + claim token; reuse the helper.
    # The new assertion: response.json()["claim_org_id"] == that org's id.
    # (Concrete fixture name depends on the existing file — search for
    # ``create_claim_token`` use within this file to find it.)
    pass
```

If the file already has end-to-end claim tests, copy one and adjust the final assertion to:

```python
    body = response.json()
    assert body["claim_org_id"] == "GB-CHC-1234567"
```

Run: `cd packages/api && pytest tests/test_open_org_claim_flow.py -v`
Expected: new test FAILS.

- [ ] **Step 2: Modify `AuthResponse`**

Edit `packages/api/src/llmstxt_api/schemas.py`:

```python
class AuthResponse(BaseModel):
    """Response after successful authentication."""

    user: UserResponse
    message: str
    # Set when the magic-link token was a claim token (carried org_id).
    # The frontend uses this to redirect into the org's editor after verify.
    claim_org_id: str | None = None
```

- [ ] **Step 3: Modify the verify endpoint**

In `packages/api/src/llmstxt_api/routes/auth.py`, in the `return AuthResponse(…)` block at the end of `verify_magic_link`, add the `claim_org_id`:

```python
    return AuthResponse(
        user=UserResponse(…unchanged…),
        message="Logged in.",
        claim_org_id=magic_token.org_id,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd packages/api && pytest tests/test_open_org_claim_flow.py tests/test_auth_cookie_domain.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/schemas.py packages/api/src/llmstxt_api/routes/auth.py packages/api/tests/test_open_org_claim_flow.py
git commit -m "feat(openorg): expose claim_org_id on AuthResponse"
```

---

## Task 6.2 — Verify page redirects to editor for claim links

**Files:**
- Modify: `packages/web/src/api/client.ts` (or wherever `AuthResponse` is typed)
- Modify: `packages/web/src/contexts/AuthContext.tsx`
- Modify: `packages/web/src/pages/AuthVerify.tsx`

The verify flow forwards `claim_org_id` from the API → AuthContext → AuthVerify. AuthVerify writes a one-time welcome flag to localStorage (`openorg.welcomeStrip.{orgId}` = `"pending"`) and navigates to `/openorg/edit/{orgId}/profile` instead of `/dashboard` when the token was a claim.

- [ ] **Step 1: Find the AuthResponse type definition**

Run: `grep -rn "claim_org_id\|class AuthResponse\|interface AuthResponse" packages/web/src/`. Open the file that defines the frontend `AuthResponse` type (most likely `packages/web/src/types.ts` or `src/api/client.ts`).

Add `claim_org_id: string | null` to that type.

- [ ] **Step 2: Pass `claim_org_id` through AuthContext.verifyToken**

In `packages/web/src/contexts/AuthContext.tsx`, change `verifyToken`'s return shape to include the claim:

```typescript
  verifyToken: (token: string) => Promise<{
    success: boolean;
    user?: User;
    message: string;
    claimOrgId?: string | null;
  }>;
```

In the implementation:

```typescript
  const verifyToken = async (token: string) => {
    setVerifying(true);
    try {
      const response = await apiClient.verifyMagicLink(token);
      await refetch();
      return {
        success: true,
        user: response.user,
        message: response.message,
        claimOrgId: response.claim_org_id ?? null,
      };
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Invalid or expired link';
      return { success: false, message };
    } finally {
      setVerifying(false);
    }
  };
```

- [ ] **Step 3: Write a failing test for AuthVerify**

```typescript
// packages/web/src/pages/AuthVerify.test.tsx (new file)
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AuthVerifyPage from './AuthVerify';

const mockVerifyToken = vi.fn();

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    verifyToken: mockVerifyToken,
    isAuthenticated: false,
  }),
}));

function renderWithToken(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/verify?token=${token}`]}>
      <Routes>
        <Route path="/auth/verify" element={<AuthVerifyPage />} />
        <Route path="/openorg/edit/:orgId/profile" element={<div data-testid="editor">editor</div>} />
        <Route path="/dashboard" element={<div data-testid="dashboard">dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AuthVerify post-claim redirect', () => {
  beforeEach(() => {
    mockVerifyToken.mockReset();
    window.localStorage.clear();
  });

  it('redirects to the editor and sets the welcome flag when claimOrgId is present', async () => {
    mockVerifyToken.mockResolvedValueOnce({
      success: true,
      message: 'ok',
      claimOrgId: 'GB-CHC-1234567',
    });
    renderWithToken('abc');
    await waitFor(() => expect(screen.getByTestId('editor')).toBeInTheDocument());
    expect(window.localStorage.getItem('openorg.welcomeStrip.GB-CHC-1234567')).toBe('pending');
  });

  it('redirects to the dashboard when there is no claimOrgId', async () => {
    mockVerifyToken.mockResolvedValueOnce({ success: true, message: 'ok' });
    renderWithToken('abc');
    await waitFor(() => expect(screen.getByTestId('dashboard')).toBeInTheDocument());
  });
});
```

Run: `cd packages/web && npm test -- AuthVerify`
Expected: FAIL — the current page redirects to `/dashboard` unconditionally.

- [ ] **Step 4: Modify `AuthVerify.tsx`**

```typescript
import { useEffect, useState } from 'react';
import { useSearchParams, Navigate, Link } from 'react-router-dom';
import { Loader2, XCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function AuthVerifyPage() {
  const [searchParams] = useSearchParams();
  const { verifyToken, isAuthenticated } = useAuth();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [errorMessage, setErrorMessage] = useState('');
  const [redirectTo, setRedirectTo] = useState<string>('/dashboard');

  const token = searchParams.get('token');

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus('error');
        setErrorMessage('No verification token provided');
        return;
      }
      const result = await verifyToken(token);
      if (result.success) {
        if (result.claimOrgId) {
          window.localStorage.setItem(`openorg.welcomeStrip.${result.claimOrgId}`, 'pending');
          setRedirectTo(`/openorg/edit/${result.claimOrgId}/profile`);
        }
        setStatus('success');
      } else {
        setStatus('error');
        setErrorMessage(result.message);
      }
    };
    verify();
  }, [token, verifyToken]);

  if (status === 'success' || isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  // unchanged body for verifying/error states …
}
```

Keep the body for verifying/error states from the existing file untouched.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd packages/web && npm test -- AuthVerify`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/web/src/pages/AuthVerify.tsx packages/web/src/pages/AuthVerify.test.tsx packages/web/src/contexts/AuthContext.tsx packages/web/src/types.ts packages/web/src/api/client.ts
git commit -m "feat(openorg): redirect post-claim verify to editor + set welcome flag"
```

(Adjust the staged-file list to match the actual files you edited for the AuthResponse type and api client.)

---

## Task 6.3 — WelcomeStrip component

**Files:**
- Create: `packages/web/src/components/openorg/WelcomeStrip.tsx`
- Create: `packages/web/src/components/openorg/WelcomeStrip.test.tsx`

One-time strip above the editor. Reads `openorg.welcomeStrip.{orgId}`; renders when value is `"pending"`. Dismiss writes `"dismissed"`.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/WelcomeStrip.test.tsx
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WelcomeStrip from './WelcomeStrip';

describe('WelcomeStrip', () => {
  beforeEach(() => window.localStorage.clear());

  it('renders when the orgId has a pending welcome flag', () => {
    window.localStorage.setItem('openorg.welcomeStrip.GB-CHC-1', 'pending');
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    expect(screen.getByText(/here's your draft/i)).toBeInTheDocument();
  });

  it('does not render when no flag is set', () => {
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    expect(screen.queryByText(/here's your draft/i)).toBeNull();
  });

  it('dismissal persists in localStorage', () => {
    window.localStorage.setItem('openorg.welcomeStrip.GB-CHC-1', 'pending');
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(window.localStorage.getItem('openorg.welcomeStrip.GB-CHC-1')).toBe('dismissed');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- WelcomeStrip`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```typescript
// packages/web/src/components/openorg/WelcomeStrip.tsx
import { useState } from 'react';

interface WelcomeStripProps {
  orgId: string;
}

function key(orgId: string) {
  return `openorg.welcomeStrip.${orgId}`;
}

export default function WelcomeStrip({ orgId }: WelcomeStripProps) {
  const [shown, setShown] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(key(orgId)) === 'pending';
  });

  if (!shown) return null;

  const handleDismiss = () => {
    window.localStorage.setItem(key(orgId), 'dismissed');
    setShown(false);
  };

  return (
    <div className="border-l-2 border-ink bg-paper-2 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <p className="max-w-prose text-sm text-ink">
          Here's your draft — pulled from public data. Have a look, edit anything
          that's off, and click Publish when you're ready. We've highlighted the
          first section we'd refine.
        </p>
        <button
          type="button"
          onClick={handleDismiss}
          className="border border-rule px-2 py-0.5 text-xs uppercase tracking-wider text-muted hover:text-ink"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- WelcomeStrip`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/WelcomeStrip.tsx packages/web/src/components/openorg/WelcomeStrip.test.tsx
git commit -m "feat(openorg): add WelcomeStrip with one-time per-org dismissal"
```

---

## Task 6.4 — Wire WelcomeStrip + start-here into EditProfile

**Files:**
- Modify: `packages/web/src/pages/openorg/EditProfile.tsx`

WelcomeStrip mounts above the EditorShell. The "Start here" badge comes from passing `startHereId` to the EditorShell — that's the first section whose tick is `●`, or fallback to first `○`.

- [ ] **Step 1: Compute `startHereId` and render WelcomeStrip**

Add imports:

```typescript
import WelcomeStrip from '../../components/openorg/WelcomeStrip';
import { computeTickStates } from '../../components/openorg/guided/tickState';
```

In the component body, compute the start-here id only while the welcome flag is `pending`:

```typescript
  const welcomePending =
    typeof window !== 'undefined' &&
    window.localStorage.getItem(`openorg.welcomeStrip.${orgId}`) === 'pending';

  const source = profile.data?.markdown ?? '';
  const startHereId = welcomePending
    ? computeTickStates(source, PROFILE_SECTIONS).find((s) => s.tick === '●')?.id ??
      computeTickStates(source, PROFILE_SECTIONS).find((s) => s.tick === '○')?.id
    : undefined;
```

Render WelcomeStrip above the EditorShell, and pass `startHereId` through:

```typescript
        <WelcomeStrip orgId={orgId} />
        <EditorShell
          kind="profile"
          initialSource={source}
          sections={PROFILE_SECTIONS}
          onSave={handleSave}
          vocabs={{ themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })) }}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save profile"
          startHereId={startHereId}
        />
```

- [ ] **Step 2: Verify build + lint**

Run: `cd packages/web && npm run build && npm run lint && npm test -- EditProfile`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add packages/web/src/pages/openorg/EditProfile.tsx
git commit -m "feat(openorg): mount WelcomeStrip + Start here on EditProfile"
```

---

## Task 6.5 — `microcopy.ts` module + sweep

**Files:**
- Create: `packages/web/src/microcopy.ts`
- Create: `packages/web/src/microcopy.test.ts`
- Modify: the components that currently hold literals (PublishStrip, SaveIndicator, WelcomeStrip, GenerateLiveStatus, Generate.tsx).

A flat keyed dictionary. Components import strings by key, not literal.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/microcopy.test.ts
import { describe, expect, it } from 'vitest';
import { t, MICROCOPY } from './microcopy';

describe('microcopy', () => {
  it('returns the string for a known key', () => {
    expect(t('publish.confirm.prompt')).toMatch(/publish this/i);
  });

  it('throws on an unknown key (typing should catch this at compile time too)', () => {
    expect(() => t('not.a.key' as keyof typeof MICROCOPY)).toThrow();
  });

  it('includes all required keys', () => {
    const required = [
      'publish.confirm.prompt',
      'publish.confirm.publish',
      'publish.confirm.notyet',
      'publish.celebrate.share',
      'publish.celebrate.copied',
      'save.justnow',
      'save.unsaved',
      'save.saving',
      'save.error',
      'save.retry',
      'generate.trust',
      'generate.timeout',
      'welcome.body',
      'welcome.dismiss',
    ];
    for (const k of required) {
      expect(MICROCOPY[k as keyof typeof MICROCOPY]).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npm test -- microcopy`
Expected: FAIL.

- [ ] **Step 3: Write `microcopy.ts`**

```typescript
// packages/web/src/microcopy.ts
/**
 * Flat keyed dictionary of user-facing strings.
 *
 * Components import strings via ``t('key')``. New copy lands here first,
 * then components import the key — never a literal. This file is the
 * single place to edit user-facing language across the Open Org flows.
 */

export const MICROCOPY = {
  'publish.confirm.prompt': 'Publish this {noun} to the federated network? Anyone will be able to see it at {url}.',
  'publish.confirm.publish': 'Publish',
  'publish.confirm.notyet': 'Not yet',
  'publish.celebrate.share': 'Share this profile ↗',
  'publish.celebrate.copied': 'Copied',
  'save.justnow': 'just now',
  'save.unsaved': 'Unsaved · ⌘S to save',
  'save.saving': 'Saving…',
  'save.error': "Couldn't save —",
  'save.retry': 'Retry',
  'generate.trust': "We won't publish anything without your say-so.",
  'generate.timeout': "Still working in the background — we'll email you when it's ready, feel free to close this tab.",
  'welcome.body': "Here's your draft — pulled from public data. Have a look, edit anything that's off, and click Publish when you're ready. We've highlighted the first section we'd refine.",
  'welcome.dismiss': 'Dismiss',
  'sidebar.missing.heading': 'Missing',
  'sidebar.starthere': 'Start here',
} as const;

export type MicrocopyKey = keyof typeof MICROCOPY;

export function t(key: MicrocopyKey, vars?: Record<string, string>): string {
  const tpl = MICROCOPY[key];
  if (!tpl) {
    throw new Error(`unknown microcopy key: ${key}`);
  }
  if (!vars) return tpl;
  return tpl.replace(/\{([a-zA-Z_]+)\}/g, (_, name) => vars[name] ?? `{${name}}`);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npm test -- microcopy`
Expected: PASS.

- [ ] **Step 5: Sweep — replace literals with `t()` calls**

In each of:

- `PublishStrip.tsx` — replace the confirm prompt, "Publish" / "Not yet" labels, "Share this profile ↗", "Copied".
- `SaveIndicator.tsx` — replace "Saving…", "Couldn't save —", "Retry", "Unsaved · ⌘S to save", "just now".
- `WelcomeStrip.tsx` — replace the body line and "Dismiss".
- `GenerateLiveStatus.tsx` — replace the 90s timeout line.
- `Generate.tsx` — replace the trust line.
- `SidebarNav.tsx` — replace "Missing" + "Start here".

Use `t('publish.confirm.prompt', { noun, url: liveUrl })` etc. Run the corresponding component test files after each swap to confirm nothing broke.

- [ ] **Step 6: Run the full suite**

Run: `cd packages/web && npm test`
Expected: green.

- [ ] **Step 7: Commit + PR gate**

```bash
git add packages/web/src/microcopy.ts packages/web/src/microcopy.test.ts packages/web/src/components/openorg/ packages/web/src/pages/openorg/Generate.tsx
git commit -m "feat(openorg): extract user-facing strings into microcopy.ts"

cd packages/web && npm run build && npm run lint && npm test
```

Expected: all green. Open PR 6 (`editor-polish-pr6-welcome`).

---

# PR 7 — Keyboard + motion polish

Goal: Cmd/Ctrl+S to save (both surfaces); `j`/`k` to move between sidebar sections; `Enter` on a section row focuses the first field in that section. Settle motion timing into named constants and audit `prefers-reduced-motion`.

Pre-flight: branch `editor-polish-pr7-polish` off `master` (after PR 6 lands).

## Task 7.1 — Keyboard shortcuts

**Files:**
- Modify: `packages/web/src/components/openorg/EditorShell.tsx`
- Modify: `packages/web/src/components/openorg/guided/GuidedEditor.tsx`
- Modify: `packages/web/src/components/openorg/guided/SidebarNav.tsx`
- Modify: matching `*.test.tsx` files

Cmd/Ctrl+S — handled at EditorShell level. On guided surface it triggers the autosave's pending source (call `save(source)` directly); on markdown surface it dispatches the existing save click.

`j`/`k` + Enter — handled in `GuidedEditor` while a section row in the sidebar has focus (via `onKeyDown` on the nav region). On `j`/`k`, change `activeId` to the next/prev section in order. On Enter, focus the first input/textarea inside the section panel.

- [ ] **Step 1: Cmd+S test**

Append to `EditorShell.test.tsx`:

```typescript
  it('saves on Cmd/Ctrl+S (guided surface)', async () => {
    vi.useFakeTimers();
    const onSave = vi.fn(async () => undefined);
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={onSave}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Y' } });
    fireEvent.keyDown(window, { key: 's', ctrlKey: true });
    expect(onSave).toHaveBeenCalled();
    vi.useRealTimers();
  });
```

Run: `cd packages/web && npm test -- EditorShell`
Expected: FAIL.

- [ ] **Step 2: Implement Cmd+S in EditorShell**

In `EditorShell.tsx`, add a `useEffect` that listens on the window:

```typescript
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isSave = (e.key === 's' || e.key === 'S') && (e.metaKey || e.ctrlKey);
      if (!isSave) return;
      e.preventDefault();
      if (surface === 'guided') {
        void onSave(source);
        return;
      }
      // On markdown surface, click the existing Save button so the dirty flag
      // clears the same way it does on a manual click.
      const btn = document.querySelector<HTMLButtonElement>(
        'button[data-testid="markdown-save"], button[type="button"][aria-busy]',
      );
      btn?.click();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [surface, onSave, source]);
```

Run: `cd packages/web && npm test -- EditorShell`
Expected: PASS.

```bash
git add packages/web/src/components/openorg/EditorShell.tsx packages/web/src/components/openorg/EditorShell.test.tsx
git commit -m "feat(openorg): save on Cmd/Ctrl+S"
```

- [ ] **Step 3: `j`/`k` navigation test**

Append to `GuidedEditor.test.tsx`:

```typescript
  it('j/k cycles the active section', () => {
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    // Default: identity. Press j twice; should be governance.
    fireEvent.keyDown(window, { key: 'j' });
    fireEvent.keyDown(window, { key: 'j' });
    expect(screen.getByText(/governance/i)).toBeInTheDocument();
    // SidebarNav active-state changes are visual; the focused-section heading
    // is the user-visible signal. Check that the active section's content
    // (e.g. Governance's "Board size" label) is now in the DOM.
    expect(screen.getByLabelText(/board size/i)).toBeInTheDocument();
  });
```

Run: `cd packages/web && npm test -- GuidedEditor`
Expected: FAIL.

- [ ] **Step 4: Implement j/k in GuidedEditor**

In `GuidedEditor.tsx`, add a `useEffect` listening on the window:

```typescript
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't interfere when typing in an input/textarea or codemirror.
      const target = e.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return;
      if (target?.closest('.cm-editor')) return;

      const idx = sections.findIndex((s) => s.id === activeId);
      if (e.key === 'j' && idx < sections.length - 1) {
        setActiveId(sections[idx + 1].id);
        e.preventDefault();
      } else if (e.key === 'k' && idx > 0) {
        setActiveId(sections[idx - 1].id);
        e.preventDefault();
      } else if (e.key === 'Enter') {
        // Focus first input/textarea inside the currently-rendered section
        // panel. Limited to the case where focus is on the document body or
        // a sidebar button — never steal Enter from a typing user.
        if (!target || target === document.body || target.tagName === 'BUTTON') {
          const first = document.querySelector<HTMLElement>(
            '[data-section-id] input, [data-section-id] textarea',
          );
          first?.focus();
          e.preventDefault();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeId, sections]);
```

Run: `cd packages/web && npm test -- GuidedEditor`
Expected: PASS.

```bash
git add packages/web/src/components/openorg/guided/GuidedEditor.tsx packages/web/src/components/openorg/guided/GuidedEditor.test.tsx
git commit -m "feat(openorg): j/k navigation between guided sections"
```

---

## Task 7.2 — Motion timing constants + reduced-motion audit

**Files:**
- Create: `packages/web/src/components/openorg/motion.ts`
- Modify: components that hard-code timing (PublishStrip, GenerateLiveStatus, EditorShell — anywhere a `duration-*` class lives).

Consolidate motion timings into one module so the spec's motion language (150-200ms fades, 200ms slides, 120ms section cross-fade, 600ms publish-celebration rule, 200ms field-flash) lives in one place and reduced-motion is consistent.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/src/components/openorg/motion.test.ts
import { describe, expect, it } from 'vitest';
import { MOTION, motionClass } from './motion';

describe('motion', () => {
  it('exposes the spec-mandated durations', () => {
    expect(MOTION.fadeMs).toBeGreaterThanOrEqual(150);
    expect(MOTION.fadeMs).toBeLessThanOrEqual(200);
    expect(MOTION.slideMs).toBe(200);
    expect(MOTION.sectionSwapMs).toBe(120);
    expect(MOTION.publishRuleMs).toBe(600);
    expect(MOTION.fieldFlashMs).toBe(200);
  });

  it('motionClass returns the right tailwind duration utility', () => {
    expect(motionClass('fade')).toContain('duration-200');
    expect(motionClass('slide')).toContain('duration-200');
    expect(motionClass('publishRule')).toContain('duration-[600ms]');
  });
});
```

Run: `cd packages/web && npm test -- motion`
Expected: FAIL.

- [ ] **Step 2: Implement `motion.ts`**

```typescript
// packages/web/src/components/openorg/motion.ts
/**
 * Motion timing constants for Open Org polish.
 *
 * Numbers come from the design spec § Motion language. Tailwind utility
 * classes are exposed via ``motionClass(kind)`` so call sites can stay
 * declarative.
 */

export const MOTION = {
  fadeMs: 200,
  slideMs: 200,
  sectionSwapMs: 120,
  publishRuleMs: 600,
  fieldFlashMs: 200,
} as const;

type MotionKind = keyof typeof MOTION;

const TAILWIND_DURATION: Record<MotionKind, string> = {
  fadeMs: 'duration-200',
  slideMs: 'duration-200',
  sectionSwapMs: 'duration-[120ms]',
  publishRuleMs: 'duration-[600ms]',
  fieldFlashMs: 'duration-200',
};

export function motionClass(kind: 'fade' | 'slide' | 'sectionSwap' | 'publishRule' | 'fieldFlash'): string {
  // Map shorthand kind → MOTION key.
  const map: Record<typeof kind, MotionKind> = {
    fade: 'fadeMs',
    slide: 'slideMs',
    sectionSwap: 'sectionSwapMs',
    publishRule: 'publishRuleMs',
    fieldFlash: 'fieldFlashMs',
  };
  return `transition ease-out ${TAILWIND_DURATION[map[kind]]} motion-reduce:transition-none`;
}
```

Run: `cd packages/web && npm test -- motion`
Expected: PASS.

- [ ] **Step 3: Use `motionClass` at existing motion sites**

Sweep through:

- `PublishStrip.tsx` — replace the hand-rolled `transition-transform duration-[600ms]` class on the celebratory gold rule with `motionClass('publishRule')`. Use `motionClass('slide')` on the confirm strip wrapper if you want a slide-in feel.
- `GenerateLiveStatus.tsx` — replace `transition-opacity duration-200` with `motionClass('fade')`.
- `GuidedEditor.tsx` — wrap the Section column in `<div className={motionClass('sectionSwap')}>` so the cross-fade duration is shared.

The `motion-reduce:transition-none` modifier comes from Tailwind out of the box; it satisfies `prefers-reduced-motion: reduce`.

- [ ] **Step 4: Manual reduced-motion smoke check**

In Chrome DevTools, Rendering panel → Emulate CSS media → `prefers-reduced-motion: reduce`. Click Publish, confirm — the gold rule should appear instantly. Switch sections in the guided editor — no cross-fade. The Save indicator field flash should still be instant per the spec ("the field-flash becomes instant under reduced motion").

- [ ] **Step 5: Commit + PR gate**

```bash
git add packages/web/src/components/openorg/motion.ts packages/web/src/components/openorg/motion.test.ts packages/web/src/components/openorg/PublishStrip.tsx packages/web/src/components/openorg/GenerateLiveStatus.tsx packages/web/src/components/openorg/guided/GuidedEditor.tsx
git commit -m "refactor(openorg): centralise motion timing constants"

cd packages/web && npm run build && npm run lint && npm test
```

Expected: green. Open PR 7 (`editor-polish-pr7-polish`). After it lands, the editor-polish work is complete.

---

# Final verification

After all seven PRs are merged, run the full project verification list from `CLAUDE.md`:

```bash
cd packages/web && npm run build && npm run lint && npm test
cd packages/api && pytest tests/
docker compose build
docker compose up
```

Visual sanity: open `http://localhost:5173/openorg/edit/GB-CHC-<test>/profile` with a dev claim link in hand, exercise the guided + markdown surfaces, publish (and unpublish) to see the celebratory state, and run through the Generate flow with a real charity number to confirm the live status panel updates.

---

# Risks & follow-ups

These were flagged during planning. They are NOT in scope for the seven PRs above; if any blocker emerges, file a small follow-up PR per item rather than re-opening one of the seven.

1. **Bridge byte-identity is per-section, not per-field.** Provenance comments inside a touched section are stripped on edit (the section's YAML block is re-emitted wholesale). This is acceptable for Phase 1; if user feedback demands per-field comment preservation we add a richer diff in a follow-up.
2. **`identity.also_known_as` schema shape.** The profile spec models it as a card list with `value`. Confirm against the JSON Schema (`org_profile.schema.json`) — if it's a flat string array, swap the section spec's `also_known_as` field to a plain card-of-string or revert it to a textarea. The bridge test won't catch this — it's a UX shape decision.
3. **Generator instrumentation depth.** PR 5 instruments the task at the start and end of the generator call only. Stage transitions like `pulling_cc` / `crawling` / `extracting_themes` are documented in the spec but not yet emitted by the task. If we want fine-grained transitions, the generator (`generate_profile_from_charity_number`) needs to accept a progress callback. Add in a follow-up if the single-stage display feels insufficient.
4. **CSRF on lookup route.** `GET /api/open-org/lookup/{number}` is anonymous and unrate-limited. The existing per-IP rate limit on POST `/generate` doesn't apply. If lookup turns into an abuse vector, add a 1 req/sec/IP token bucket in a follow-up; CC's own rate limit absorbs accidental hammering meanwhile.
5. **`useGenerateStatus` cache lifetime.** The query keeps polling at 2s while `status` is `pending`/`generating`. If a tab is left open across a worker restart that loses the in-flight generation, the row will sit in `generating` forever. Acceptable for Phase 1; consider adding a server-side stale-job sweeper in a follow-up.
6. **Mobile/narrow sidebar layout.** The spec calls for the sidebar to collapse to a sticky top strip with horizontal scroll on `<lg`. The plan currently leaves the sidebar stacked above the section panel on mobile (acceptable but not the spec's vision). Add a small mobile-specific component in a follow-up if user testing surfaces the gap.
7. **Static vocabs vs. catalogue.** PR 4 task 4.7 hard-codes the non-theme pill vocabs (`beneficiaries`, `status`, `horizon`, `access_level`, `connections`). These should eventually come from the JSON Schema enums or a server-side catalogue. Follow-up PR can replace the static module with a `/api/open-org/vocabs` endpoint once the catalogue is settled.
