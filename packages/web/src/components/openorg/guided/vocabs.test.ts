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
