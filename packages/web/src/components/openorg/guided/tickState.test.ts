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
