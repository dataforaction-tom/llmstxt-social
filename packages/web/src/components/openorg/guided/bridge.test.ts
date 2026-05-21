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
