import { describe, it, expect } from 'vitest';
import { hasValidGeolocation } from './discoverGeo';

describe('hasValidGeolocation', () => {
  it('accepts finite numeric lat/lon', () => {
    expect(hasValidGeolocation({ geolocation: { lat: 51.5, lon: -0.1 } })).toBe(true);
  });

  it('rejects null / missing geolocation', () => {
    expect(hasValidGeolocation({ geolocation: null })).toBe(false);
    expect(hasValidGeolocation({})).toBe(false);
  });

  it('rejects partial or non-numeric coordinates (the white-screen case)', () => {
    expect(hasValidGeolocation({ geolocation: { lat: 51.5 } })).toBe(false);
    expect(hasValidGeolocation({ geolocation: { lat: '51.5', lon: '-0.1' } })).toBe(false);
    expect(hasValidGeolocation({ geolocation: { lat: NaN, lon: 0 } })).toBe(false);
  });
});
