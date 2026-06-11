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
