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
