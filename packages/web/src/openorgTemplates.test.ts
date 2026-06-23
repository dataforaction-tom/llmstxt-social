import { describe, it, expect } from 'vitest';
import { NEW_STRATEGY_TEMPLATE, NEW_IDEA_TEMPLATE } from './openorgTemplates';

// Schema enums (packages/core/.../schemas/org_{strategy,idea}.schema.json).
const STRATEGY_STATUS = ['draft', 'active', 'archived'];
const IDEA_STATUS = ['seed', 'developing', 'shaped', 'delivered', 'archived'];

function statusComment(template: string): string {
  const line = template.split('\n').find((l) => l.trimStart().startsWith('status:'));
  return line ?? '';
}

describe('Open Org blank templates', () => {
  it('strategy status default is a valid enum value', () => {
    const value = statusComment(NEW_STRATEGY_TEMPLATE).match(/status:\s*(\w+)/)?.[1];
    expect(STRATEGY_STATUS).toContain(value);
  });

  it('strategy status guidance only lists valid enum values', () => {
    // The "# a | b | c" hint must not advertise values the schema rejects on save.
    const comment = statusComment(NEW_STRATEGY_TEMPLATE);
    const advertised = (comment.split('#')[1] ?? '')
      .split('|')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const v of advertised) expect(STRATEGY_STATUS).toContain(v);
  });

  it('idea status guidance only lists valid enum values', () => {
    const comment = statusComment(NEW_IDEA_TEMPLATE);
    const advertised = (comment.split('#')[1] ?? '')
      .split('|')
      .map((s) => s.trim())
      .filter(Boolean);
    expect(advertised.length).toBeGreaterThan(0);
    for (const v of advertised) expect(IDEA_STATUS).toContain(v);
  });

  it('strategy priorities live in frontmatter, not a dropped body heading', () => {
    // The converter only captures `priorities` from YAML frontmatter; a
    // `## Priority` body heading is silently lost on save.
    expect(NEW_STRATEGY_TEMPLATE).toContain('priorities:');
    expect(NEW_STRATEGY_TEMPLATE).not.toMatch(/^##\s+Priority/m);
  });
});
