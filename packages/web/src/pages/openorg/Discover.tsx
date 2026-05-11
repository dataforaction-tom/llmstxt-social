/**
 * Open Org discovery page.
 *
 * Public, no auth. Lists local + federated profiles with theme / area / free-
 * text filters and a Leaflet map of geolocated entries. Cursor pagination via
 * a "Load more" button.
 *
 * Route: /openorg/discover
 */

import { useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import {
  type DiscoveryFilters,
  type DiscoveryRow,
  fetchDiscoveryPage,
  useDiscoveryFirstPage,
  useThemes,
} from '../../api/openorg';

// Vite-bundled Leaflet default-marker assets — Leaflet's own image URLs assume
// they live alongside the script, which isn't true in a Vite build.
import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
});

const DEFAULT_LIMIT = 20;
// Centre of the UK; first paint before any results have geolocations.
const UK_CENTRE: [number, number] = [54.0, -2.5];

export default function DiscoverPage() {
  const [filters, setFilters] = useState<DiscoveryFilters>({});
  const [draftQ, setDraftQ] = useState('');
  const [draftAreaCode, setDraftAreaCode] = useState('');
  const [extraPages, setExtraPages] = useState<DiscoveryRow[]>([]);
  const [pageCursor, setPageCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const themes = useThemes();
  const firstPage = useDiscoveryFirstPage(filters, DEFAULT_LIMIT);

  // Reset extra pages when the filter set changes — TanStack's cache for
  // (filters,limit) is the source of truth for the *first* page; later pages
  // we manage in component state.
  useMemo(() => {
    setExtraPages([]);
    setPageCursor(firstPage.data?.next_cursor ?? null);
  }, [firstPage.data]);

  const allRows: DiscoveryRow[] = useMemo(() => {
    const base = firstPage.data?.results ?? [];
    return [...base, ...extraPages];
  }, [firstPage.data, extraPages]);

  const mapped = allRows.filter((r) => r.geolocation !== null);

  function applyFilter(next: Partial<DiscoveryFilters>) {
    setFilters((prev) => {
      const merged = { ...prev, ...next };
      // Strip empty string filters so the cache key stays clean.
      (Object.keys(merged) as Array<keyof DiscoveryFilters>).forEach((k) => {
        if (!merged[k]) delete merged[k];
      });
      return merged;
    });
  }

  async function handleLoadMore() {
    if (!pageCursor) return;
    setLoadingMore(true);
    try {
      const page = await fetchDiscoveryPage(filters, pageCursor, DEFAULT_LIMIT);
      setExtraPages((prev) => [...prev, ...page.results]);
      setPageCursor(page.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <Helmet>
        <title>Discover organisations · Open Org</title>
        <meta
          name="description"
          content="Search Open Org-published UK social-sector organisations by theme, place, and keyword."
        />
      </Helmet>

      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Discover organisations</h1>
        <p className="mt-1 text-sm text-gray-600">
          Profiles published in the Open Org format, drawn from this site and the
          federated Murmurations index.
        </p>
      </header>

      <form
        className="mb-6 grid gap-3 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          applyFilter({ q: draftQ, areaCode: draftAreaCode });
        }}
      >
        <label className="text-sm">
          <span className="block text-gray-700">Search</span>
          <input
            type="text"
            className="mt-1 w-full rounded border border-gray-300 px-2 py-1"
            placeholder="Name or area"
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
          />
        </label>

        <label className="text-sm">
          <span className="block text-gray-700">Theme</span>
          <select
            className="mt-1 w-full rounded border border-gray-300 px-2 py-1"
            value={filters.theme ?? ''}
            onChange={(e) => applyFilter({ theme: e.target.value })}
          >
            <option value="">All themes</option>
            {themes.data?.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="block text-gray-700">ONS area code</span>
          <input
            type="text"
            className="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono"
            placeholder="E.g. E92000001"
            value={draftAreaCode}
            onChange={(e) => setDraftAreaCode(e.target.value)}
          />
        </label>

        <div className="sm:col-span-3">
          <button
            type="submit"
            className="rounded bg-primary-600 px-3 py-1.5 text-sm text-white hover:bg-primary-700"
          >
            Apply
          </button>
          <button
            type="button"
            className="ml-2 rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => {
              setFilters({});
              setDraftQ('');
              setDraftAreaCode('');
            }}
          >
            Reset
          </button>
        </div>
      </form>

      {mapped.length > 0 && (
        <div className="mb-6 h-80 overflow-hidden rounded border border-gray-200">
          <MapContainer
            center={UK_CENTRE}
            zoom={6}
            scrollWheelZoom={false}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {mapped.map((row) => (
              <Marker
                key={row.org_id}
                position={[row.geolocation!.lat, row.geolocation!.lon]}
              >
                <Popup>
                  <strong>{row.name}</strong>
                  {row.primary_area ? <div>{row.primary_area}</div> : null}
                  <a className="text-primary-700 underline" href={row.profile_url}>
                    View profile
                  </a>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      )}

      {firstPage.isLoading ? (
        <div className="py-12 text-center text-gray-500">Loading…</div>
      ) : firstPage.isError ? (
        <div className="py-12 text-center text-red-700">
          Couldn't load profiles. Please try again.
        </div>
      ) : allRows.length === 0 ? (
        <div className="py-12 text-center text-gray-500">
          No organisations match. Try a different filter.
        </div>
      ) : (
        <>
          <ul className="grid gap-3 sm:grid-cols-2">
            {allRows.map((row) => (
              <li
                key={row.org_id}
                className="rounded border border-gray-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-lg font-semibold text-gray-900">{row.name}</h2>
                  <span
                    className={
                      'rounded-full px-2 py-0.5 text-xs ' +
                      (row.source === 'local'
                        ? 'bg-primary-50 text-primary-700'
                        : 'bg-gray-100 text-gray-700')
                    }
                  >
                    {row.source}
                  </span>
                </div>
                {row.primary_area ? (
                  <p className="mt-1 text-sm text-gray-600">{row.primary_area}</p>
                ) : null}
                {row.summary ? (
                  <p className="mt-2 text-sm text-gray-700 line-clamp-3">{row.summary}</p>
                ) : null}
                {row.themes.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {row.themes.slice(0, 5).map((t) => (
                      <span
                        key={t}
                        className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}
                <a
                  className="mt-3 inline-block text-sm text-primary-700 underline"
                  href={row.profile_url}
                >
                  View profile JSON →
                </a>
              </li>
            ))}
          </ul>
          {pageCursor ? (
            <div className="mt-6 text-center">
              <button
                type="button"
                disabled={loadingMore}
                onClick={handleLoadMore}
                className="rounded border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
