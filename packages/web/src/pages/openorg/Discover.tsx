/**
 * Open Org discovery page.
 *
 * Public, no auth. Lists local + federated profiles with theme / area / free-
 * text filters and a Leaflet map of geolocated entries. Cursor pagination via
 * a "Load more" button.
 *
 * Route: /openorg/discover
 *
 * Design: civic editorial. Warm paper background, Fraunces display heads,
 * Public Sans body, hairline rules, small-caps kickers. Staggered card
 * reveal on first paint.
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

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
});

const DEFAULT_LIMIT = 20;
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

  const totalCount = allRows.length;
  const activeFilterChips = [
    filters.theme && { label: filters.theme, key: 'theme' as const },
    filters.areaCode && { label: filters.areaCode, key: 'areaCode' as const },
    filters.q && { label: `"${filters.q}"`, key: 'q' as const },
  ].filter(Boolean) as { label: string; key: keyof DiscoveryFilters }[];

  return (
    <div className="surface-paper min-h-screen">
      <Helmet>
        <title>Discover · Open Org</title>
        <meta
          name="description"
          content="Search Open Org-published UK social-sector organisations by theme, place, and keyword."
        />
      </Helmet>

      <div className="mx-auto max-w-6xl px-6 py-12">
        {/* --- editorial header --------------------------------------- */}
        <header className="mb-10">
          <div className="kicker num">Discovery · Open Org</div>
          <h1 className="display-head mt-2 text-4xl font-medium leading-[1.05] sm:text-5xl">
            Find UK social-sector
            <br />
            organisations by what they do.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-muted">
            Profiles published in the Open Org format, drawn from this site
            and the federated Murmurations index. Filter by theme, place, or
            keyword.
          </p>
        </header>

        {/* --- filter band --------------------------------------------- */}
        <form
          className="rule-h border-b border-rule pb-6 pt-6"
          onSubmit={(e) => {
            e.preventDefault();
            applyFilter({ q: draftQ, areaCode: draftAreaCode });
          }}
        >
          <div className="grid items-end gap-4 sm:grid-cols-[1fr_1fr_1fr_auto]">
            <label className="block">
              <span className="kicker">Search</span>
              <input
                type="text"
                className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-ink placeholder:text-muted focus:border-ink focus:outline-none focus:ring-0"
                placeholder="Name or area"
                value={draftQ}
                onChange={(e) => setDraftQ(e.target.value)}
              />
            </label>

            <label className="block">
              <span className="kicker">Theme</span>
              <select
                className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-ink focus:border-ink focus:outline-none focus:ring-0"
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

            <label className="block">
              <span className="kicker">ONS area code</span>
              <input
                type="text"
                className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 font-mono text-sm text-ink placeholder:text-muted focus:border-ink focus:outline-none focus:ring-0"
                placeholder="E92000001"
                value={draftAreaCode}
                onChange={(e) => setDraftAreaCode(e.target.value)}
              />
            </label>

            <div className="flex gap-3">
              <button
                type="submit"
                className="bg-ink px-4 py-2 text-sm font-medium text-paper transition hover:bg-primary-700"
              >
                Apply
              </button>
              <button
                type="button"
                className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
                onClick={() => {
                  setFilters({});
                  setDraftQ('');
                  setDraftAreaCode('');
                }}
              >
                Reset
              </button>
            </div>
          </div>

          {activeFilterChips.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
              <span className="kicker">Active</span>
              {activeFilterChips.map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  onClick={() => applyFilter({ [chip.key]: undefined } as Partial<DiscoveryFilters>)}
                  className="group inline-flex items-center gap-1.5 border border-rule bg-paper-2 px-2 py-0.5 text-ink hover:border-ink"
                >
                  <span className="font-mono">{chip.label}</span>
                  <span className="text-muted group-hover:text-ink">×</span>
                </button>
              ))}
            </div>
          )}
        </form>

        {/* --- map (only when there's something to plot) -------------- */}
        {mapped.length > 0 && (
          <section className="mt-10">
            <div className="kicker num mb-2">Map · {mapped.length} located</div>
            <div className="overflow-hidden border border-rule">
              <MapContainer
                center={UK_CENTRE}
                zoom={6}
                scrollWheelZoom={false}
                style={{ height: '320px', width: '100%' }}
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
                      <div className="font-display text-base text-ink">{row.name}</div>
                      {row.primary_area ? (
                        <div className="text-xs text-muted">{row.primary_area}</div>
                      ) : null}
                      <a
                        className="text-xs text-primary-700 underline"
                        href={`/openorg/${row.org_id}`}
                      >
                        View profile
                      </a>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>
          </section>
        )}

        {/* --- results -------------------------------------------------- */}
        <section className="mt-10">
          <div className="kicker num mb-4 flex items-baseline justify-between">
            <span>
              Results · {totalCount}
              {pageCursor ? '+' : ''}
            </span>
            {firstPage.isFetching && !firstPage.isLoading ? (
              <span className="text-muted">Updating…</span>
            ) : null}
          </div>

          {firstPage.isLoading ? (
            <div className="py-16 text-center text-muted">Loading…</div>
          ) : firstPage.isError ? (
            <div className="py-16 text-center text-red-700">
              Couldn't load profiles. Please try again.
            </div>
          ) : allRows.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-display text-2xl text-ink">No matches.</p>
              <p className="mt-2 text-sm text-muted">
                Try fewer filters, or a broader area.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-rule border-y border-rule">
              {allRows.map((row, i) => (
                <li
                  key={row.org_id}
                  className="grid grid-cols-[1fr_auto] items-start gap-6 py-6"
                  style={{
                    animation: 'discoverFadeIn 320ms ease-out both',
                    animationDelay: `${Math.min(i, 12) * 35}ms`,
                  }}
                >
                  <div>
                    <a
                      href={`/openorg/${row.org_id}`}
                      className="display-head text-2xl font-medium leading-tight text-ink hover:text-primary-700"
                    >
                      {row.name}
                    </a>
                    {row.primary_area ? (
                      <p className="mt-0.5 text-sm italic text-muted">
                        {row.primary_area}
                      </p>
                    ) : null}
                    {row.summary ? (
                      <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink/90 line-clamp-3">
                        {row.summary}
                      </p>
                    ) : null}
                    {row.themes.length > 0 ? (
                      <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
                        {row.themes.slice(0, 6).map((t) => (
                          <li key={t} className="font-mono">
                            #{t}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>

                  <div className="flex flex-col items-end gap-2 text-right">
                    <span
                      className={
                        'kicker num ' +
                        (row.source === 'local' ? 'text-primary-700' : 'text-muted')
                      }
                    >
                      {row.source}
                    </span>
                    <a
                      href={row.profile_url}
                      className="text-xs text-muted underline-offset-4 hover:text-ink hover:underline"
                    >
                      profile.json →
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {pageCursor ? (
            <div className="mt-10 text-center">
              <button
                type="button"
                disabled={loadingMore}
                onClick={handleLoadMore}
                className="border border-rule bg-paper px-5 py-2 text-sm text-ink transition hover:bg-paper-2 disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            </div>
          ) : null}
        </section>
      </div>

      {/* keyframes inline so the page is self-contained */}
      <style>{`
        @keyframes discoverFadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
