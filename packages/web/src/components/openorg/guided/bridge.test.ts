import { describe, expect, it } from 'vitest';
import {
  spliceFrontmatterKey,
  spliceBodySection,
  parseSection,
  applySectionEdit,
  type SectionSpec,
} from './bridge';

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
    parsed.yaml.identity = { ...(parsed.yaml.identity as Record<string, unknown>), name: 'Riverside Community Trust' };
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
