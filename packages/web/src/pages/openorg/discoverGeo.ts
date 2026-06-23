/**
 * Geolocation guards for the Discovery map.
 *
 * Federated rows (ExternalOrgCache) pass their geolocation through unvalidated,
 * so at runtime `lat`/`lon` can be missing or non-numeric even though the type
 * says `{lat: number; lon: number} | null`. Feeding NaN/undefined into Leaflet's
 * `position` throws and white-screens the whole page — guard before mapping.
 */

export interface MaybeGeo {
  geolocation?: { lat?: unknown; lon?: unknown } | null;
}

export function hasValidGeolocation(row: MaybeGeo): boolean {
  const geo = row.geolocation;
  if (!geo) return false;
  return (
    typeof geo.lat === 'number' &&
    Number.isFinite(geo.lat) &&
    typeof geo.lon === 'number' &&
    Number.isFinite(geo.lon)
  );
}
