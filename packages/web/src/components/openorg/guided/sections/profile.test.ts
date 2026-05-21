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
    const themes = mission.fields.find((f) => f.key === 'mission.themes')!;
    expect(themes.kind).toBe('pills');
    expect(themes.selectionCap).toBe(6);
  });

  it('values section owns a top-level array, not a yaml subkey', () => {
    const values = PROFILE_SECTIONS.find((s) => s.id === 'values')!;
    expect(values.yamlKeys).toEqual(['values']);
  });
});
