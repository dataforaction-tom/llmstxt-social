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
