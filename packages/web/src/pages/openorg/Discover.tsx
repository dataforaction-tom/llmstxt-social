/**
 * Open Org discovery page — ideas-first.
 *
 * The essay envisions funders browsing "a landscape of ideas". Ideas are the
 * primary surface; the organisation directory and graph are secondary lenses.
 *
 * Route: /openorg/discover
 *
 * Three views, defaulting to Ideas:
 *   - Ideas  — hero summary, theme chips, place/status filters, idea cards
 *   - Orgs   — the original organisation list + Leaflet map (secondary lens)
 *   - Graph  — D3 force-directed graph (lazy-loaded)
 *
 * Design: Good Ship brand. Cream background, Fraunces display heads,
 * DM Sans body, hairline rules, small-caps kickers.
 */

import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import {
  type DiscoveryFilters,
  type DiscoveryRow,
  type IdeaFilters,
  type IdeaRow,
  type IdeaSort,
  type IdeasSummary,
  fetchDiscoveryPage,
  fetchIdeasPage,
  useDiscoveryFirstPage,
  useIdeasFirstPage,
  useIdeasSummary,
  useThemes,
} from '../../api/openorg';

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';
import { hasValidGeolocation } from './discoverGeo';

// Lazy-load the graph view — D3 is ~50KB and only needed when the user
// switches to graph mode.
const GraphDiscovery = lazy(() => import('../../components/openorg/GraphDiscovery'));

type ViewMode = 'ideas' | 'list' | 'graph';

L.Icon.Default.mergeOptions({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
});

const DEFAULT_LIMIT = 20;
const IDEAS_LIMIT = 60;
const UK_CENTRE: [number, number] = [54.0, -2.5];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Any status' },
  { value: 'seed', label: 'Seed' },
  { value: 'developing', label: 'Developing' },
  { value: 'shaped', label: 'Shaped' },
  { value: 'delivered', label: 'Delivered' },
];

const SORT_OPTIONS: { value: IdeaSort; label: string }[] = [
  { value: 'signals', label: 'Most interest' },
  { value: 'recent', label: 'Recent' },
  { value: 'status', label: 'Maturity' },
];

export default function DiscoverPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('ideas');

  return (
    <div className="surface-cream min-h-screen">
      <Helmet>
        <title>Discover · Open Org</title>
        <meta
          name="description"
          content="Browse a landscape of ideas from UK social-sector organisations. Filter by theme, place, and status."
        />
      </Helmet>

      <div className="mx-auto max-w-6xl px-6 py-12">
        {/* --- editorial header --------------------------------------- */}
        <header className="mb-10">
          <div className="kicker num">Discovery · Open Org</div>
          <h1 className="display-head mt-2 text-4xl font-medium leading-[1.05] sm:text-5xl">
            A landscape of ideas,
            <br />
            across UK social-sector organisations.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-grey-blue">
            Browse published ideas by theme, place, and status. See where
            funders are signalling interest, and find the work that connects
            to your priorities.
          </p>
        </header>

        {/* --- view toggle --------------------------------------------- */}
        <div className="mt-2 mb-6 flex items-center gap-2">
          <span className="kicker">View</span>
          {(['ideas', 'list', 'graph'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              className={
                'px-3 py-1 text-sm transition ' +
                (viewMode === mode
                  ? 'bg-navy text-cream'
                  : 'border border-rule text-navy hover:bg-cream-dark')
              }
              onClick={() => setViewMode(mode)}
            >
              {mode === 'ideas' ? 'Ideas' : mode === 'list' ? 'Organisations' : 'Graph'}
            </button>
          ))}
        </div>

        {viewMode === 'ideas' && <IdeasLandscape />}
        {viewMode === 'list' && <OrgDirectory />}
        {viewMode === 'graph' && (
          <section className="mt-10">
            <Suspense
              fallback={
                <div className="py-16 text-center text-grey-blue">
                  Loading graph…
                </div>
              }
            >
              <GraphDiscovery />
            </Suspense>
          </section>
        )}
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

// --------------------------------------------------------------------------- //
// Ideas landscape — the default view
// --------------------------------------------------------------------------- //

function IdeasLandscape() {
  const themesQuery = useThemes();
  const summaryQuery = useIdeasSummary();

  // Multi-select theme chips.
  const [selectedThemes, setSelectedThemes] = useState<string[]>([]);
  const [placeQuery, setPlaceQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sort, setSort] = useState<IdeaSort>('signals');
  const [extraRows, setExtraRows] = useState<IdeaRow[]>([]);
  const [pageCursor, setPageCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  // The API takes a single theme param; we filter client-side for multi-select.
  // We send the first selected theme to narrow server-side, then refine here.
  const apiTheme = selectedThemes[0] || undefined;
  const filters: IdeaFilters = {
    theme: apiTheme,
    status: statusFilter || undefined,
    q: placeQuery || undefined,
    sort,
  };

  const firstPage = useIdeasFirstPage(filters, IDEAS_LIMIT);

  useEffect(() => {
    setExtraRows([]);
    setPageCursor(firstPage.data?.next_cursor ?? null);
  }, [firstPage.data]);

  const allRows: IdeaRow[] = useMemo(() => {
    const base = firstPage.data?.results ?? [];
    return [...base, ...extraRows];
  }, [firstPage.data, extraRows]);

  // Client-side refinement for multi-theme select.
  const visibleRows = useMemo(() => {
    if (selectedThemes.length <= 1) return allRows;
    const themeSet = new Set(selectedThemes);
    return allRows.filter((r) => r.themes.some((t) => themeSet.has(t)));
  }, [allRows, selectedThemes]);

  async function handleLoadMore() {
    if (!pageCursor) return;
    setLoadingMore(true);
    try {
      const page = await fetchIdeasPage(filters, pageCursor, IDEAS_LIMIT);
      setExtraRows((prev) => [...prev, ...page.results]);
      setPageCursor(page.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  }

  function toggleTheme(themeKey: string) {
    setSelectedThemes((prev) =>
      prev.includes(themeKey)
        ? prev.filter((t) => t !== themeKey)
        : [...prev, themeKey],
    );
  }

  function resetFilters() {
    setSelectedThemes([]);
    setPlaceQuery('');
    setStatusFilter('');
  }

  const summary: IdeasSummary | undefined = summaryQuery.data;
  // Use the summary breakdown for chip counts when available; fall back to
  // the theme vocabulary (no counts).
  const themeChipData = useMemo(() => {
    const themeChips = themesQuery.data ?? [];
    if (summary && Object.keys(summary.themes_breakdown).length > 0) {
      return themeChips
        .map((t) => ({ ...t, count: summary.themes_breakdown[t.key] ?? 0 }))
        .filter((t) => t.count > 0)
        .sort((a, b) => b.count - a.count);
    }
    return themeChips.map((t) => ({ ...t, count: 0 }));
  }, [themesQuery.data, summary]);

  return (
    <section className="mt-2" data-testid="ideas-landscape">
      {/* --- hero summary ------------------------------------------------- */}
      <div className="border-b border-rule pb-6" data-testid="ideas-summary">
        {summaryQuery.isLoading ? (
          <p className="text-sm text-grey-blue">Loading landscape…</p>
        ) : summaryQuery.isError ? (
          <p className="text-sm text-grey-blue">Couldn't load summary.</p>
        ) : summary ? (
          <p className="display-head text-2xl font-medium text-navy">
            <span data-testid="summary-ideas-count">{summary.total_ideas}</span>{' '}
            ideas from{' '}
            <span data-testid="summary-orgs-count">{summary.total_orgs}</span>{' '}
            organisations across{' '}
            <span data-testid="summary-themes-count">
              {Object.keys(summary.themes_breakdown).length}
            </span>{' '}
            themes
          </p>
        ) : null}
      </div>

      {/* --- theme chips (multi-select) ----------------------------------- */}
      {themeChipData.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2" data-testid="theme-chips">
          <span className="kicker">Themes</span>
          {themeChipData.map((t) => {
            const active = selectedThemes.includes(t.key);
            return (
              <button
                key={t.key}
                type="button"
                data-theme-chip={t.key}
                aria-pressed={active}
                onClick={() => toggleTheme(t.key)}
                className={
                  'inline-flex items-center gap-1.5 border px-2.5 py-1 text-xs transition ' +
                  (active
                    ? 'border-navy bg-navy text-cream'
                    : 'border-rule bg-cream text-navy hover:border-navy')
                }
              >
                <span>{t.label}</span>
                {t.count > 0 && (
                  <span
                    className={active ? 'text-cream/70' : 'text-grey-blue'}
                    data-theme-count={t.key}
                  >
                    {t.count}
                  </span>
                )}
              </button>
            );
          })}
          {selectedThemes.length > 0 && (
            <button
              type="button"
              onClick={resetFilters}
              className="text-xs text-grey-blue underline-offset-4 hover:text-navy hover:underline"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* --- place + status + sort filters -------------------------------- */}
      <form
        className="mt-6 grid items-end gap-4 border-b border-rule pb-6 sm:grid-cols-[1fr_auto_auto_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          // placeQuery is already live; this just keeps the form semantics.
        }}
      >
        <label className="block">
          <span className="kicker">Place or keyword</span>
          <input
            type="text"
            className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-navy placeholder:text-grey-blue focus:border-navy focus:outline-none focus:ring-0"
            placeholder="Place name or keyword…"
            value={placeQuery}
            onChange={(e) => setPlaceQuery(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="kicker">Status</span>
          <select
            className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-navy focus:border-navy focus:outline-none focus:ring-0"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="kicker">Sort</span>
          <select
            className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-navy focus:border-navy focus:outline-none focus:ring-0"
            value={sort}
            onChange={(e) => setSort(e.target.value as IdeaSort)}
          >
            {SORT_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        {(selectedThemes.length > 0 || placeQuery || statusFilter) && (
          <button
            type="button"
            className="text-sm text-grey-blue underline-offset-4 hover:text-navy hover:underline"
            onClick={resetFilters}
          >
            Reset
          </button>
        )}
      </form>

      {/* --- idea cards grid ---------------------------------------------- */}
      <div className="mt-6 mb-4 flex items-baseline justify-between">
        <span className="kicker num">
          Ideas · {visibleRows.length}
          {pageCursor ? '+' : ''}
        </span>
        {firstPage.isFetching && !firstPage.isLoading ? (
          <span className="text-xs text-grey-blue">Updating…</span>
        ) : null}
      </div>

      {firstPage.isLoading ? (
        <div className="py-16 text-center text-grey-blue">Loading ideas…</div>
      ) : firstPage.isError ? (
        <div className="py-16 text-center text-red-700">
          Couldn't load ideas. Please try again.
        </div>
      ) : visibleRows.length === 0 ? (
        <div className="py-16 text-center">
          <p className="font-display text-2xl text-navy">No ideas match.</p>
          <p className="mt-2 text-sm text-grey-blue">
            Try fewer filters, or a broader place.
          </p>
        </div>
      ) : (
        <ul
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          data-testid="idea-grid"
        >
          {visibleRows.map((row, i) => (
            <li
              key={`${row.org_id}-${row.slug}`}
              data-idea-card={`${row.org_id}-${row.slug}`}
              className="flex flex-col border border-rule bg-cream-dark/40 p-4 transition hover:border-navy"
              style={{
                animation: 'discoverFadeIn 320ms ease-out both',
                animationDelay: `${Math.min(i, 12) * 35}ms`,
              }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="display-head text-lg font-medium leading-tight text-navy">
                  <Link
                    to={`/openorg/${row.org_id}/ideas/${row.slug}`}
                    className="hover:text-teal"
                  >
                    {row.slug}
                  </Link>
                </h3>
                {row.status && (
                  <span
                    className="shrink-0 text-[10px] uppercase tracking-wider text-grey-blue"
                    data-idea-status={row.status}
                  >
                    {row.status}
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-grey-blue">
                <Link
                  to={`/openorg/${row.org_id}`}
                  className="hover:text-navy hover:underline"
                >
                  {row.org_name}
                </Link>
                {row.primary_area ? ` · ${row.primary_area}` : ''}
              </p>
              {row.summary && (
                <p className="mt-2 text-sm leading-relaxed text-navy/90 line-clamp-3">
                  {row.summary}
                </p>
              )}
              {row.themes.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-x-2 gap-y-1 text-[11px] text-grey-blue">
                  {row.themes.slice(0, 4).map((t) => (
                    <li key={t} className="font-mono">
                      #{t}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-auto flex items-center justify-between gap-2 pt-3 text-xs">
                <div className="flex items-center gap-3">
                  {(row.cost_lower || row.cost_upper) && (
                    <span className="text-grey-blue" data-idea-cost>
                      {row.cost_currency ?? 'GBP'}{' '}
                      {row.cost_lower?.toLocaleString() ?? '?'}–
                      {row.cost_upper?.toLocaleString() ?? '?'}
                    </span>
                  )}
                  {row.signal_count > 0 && (
                    <span
                      className="text-teal"
                      data-idea-signals
                      title={`${row.signal_count} funder signal${row.signal_count === 1 ? '' : 's'}`}
                    >
                      {row.signal_count} interested
                    </span>
                  )}
                </div>
                <Link
                  to={`/openorg/${row.org_id}/ideas/${row.slug}`}
                  className="text-grey-blue underline-offset-4 hover:text-navy hover:underline"
                >
                  View idea →
                </Link>
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
            className="border border-rule bg-cream px-5 py-2 text-sm text-navy transition hover:bg-cream-dark disabled:opacity-50"
          >
            {loadingMore ? 'Loading…' : 'Load more'}
          </button>
        </div>
      ) : null}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Organisation directory — secondary lens (original list + map)
// --------------------------------------------------------------------------- //

function OrgDirectory() {
  const [filters, setFilters] = useState<DiscoveryFilters>({});
  const [draftQ, setDraftQ] = useState('');
  const [draftAreaCode, setDraftAreaCode] = useState('');
  const [extraPages, setExtraPages] = useState<DiscoveryRow[]>([]);
  const [pageCursor, setPageCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const themes = useThemes();
  const firstPage = useDiscoveryFirstPage(filters, DEFAULT_LIMIT);

  useEffect(() => {
    setExtraPages([]);
    setPageCursor(firstPage.data?.next_cursor ?? null);
  }, [firstPage.data]);

  const allRows: DiscoveryRow[] = useMemo(() => {
    const base = firstPage.data?.results ?? [];
    return [...base, ...extraPages];
  }, [firstPage.data, extraPages]);

  const mapped = allRows.filter(hasValidGeolocation);

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
    <section className="mt-2">
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
              className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-navy placeholder:text-grey-blue focus:border-navy focus:outline-none focus:ring-0"
              placeholder="Name or area"
              value={draftQ}
              onChange={(e) => setDraftQ(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="kicker">Theme</span>
            <select
              className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 text-base text-navy focus:border-navy focus:outline-none focus:ring-0"
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
              className="mt-1.5 w-full border-0 border-b border-rule bg-transparent pb-1.5 font-mono text-sm text-navy placeholder:text-grey-blue focus:border-navy focus:outline-none focus:ring-0"
              placeholder="E92000001"
              value={draftAreaCode}
              onChange={(e) => setDraftAreaCode(e.target.value)}
            />
          </label>

          <div className="flex gap-3">
            <button
              type="submit"
              className="bg-teal px-4 py-2 text-sm font-medium text-cream transition hover:bg-teal-light"
            >
              Apply
            </button>
            <button
              type="button"
              className="text-sm text-grey-blue underline-offset-4 hover:text-navy hover:underline"
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
                className="group inline-flex items-center gap-1.5 border border-rule bg-cream-dark px-2 py-0.5 text-navy hover:border-navy"
              >
                <span className="font-mono">{chip.label}</span>
                <span className="text-grey-blue group-hover:text-navy">×</span>
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
                    <div className="font-display text-base text-navy">{row.name}</div>
                    {row.primary_area ? (
                      <div className="text-xs text-grey-blue">{row.primary_area}</div>
                    ) : null}
                    <a
                      className="text-xs text-teal underline"
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
            <span className="text-grey-blue">Updating…</span>
          ) : null}
        </div>

        {firstPage.isLoading ? (
          <div className="py-16 text-center text-grey-blue">Loading…</div>
        ) : firstPage.isError ? (
          <div className="py-16 text-center text-red-700">
            Couldn't load profiles. Please try again.
          </div>
        ) : allRows.length === 0 ? (
          <div className="py-16 text-center">
            <p className="font-display text-2xl text-navy">No matches.</p>
            <p className="mt-2 text-sm text-grey-blue">
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
                    className="display-head text-2xl font-medium leading-tight text-navy hover:text-teal"
                  >
                    {row.name}
                  </a>
                  {row.primary_area ? (
                    <p className="mt-0.5 text-sm italic text-grey-blue">
                      {row.primary_area}
                    </p>
                  ) : null}
                  {row.summary ? (
                    <p className="mt-2 max-w-prose text-sm leading-relaxed text-navy/90 line-clamp-3">
                      {row.summary}
                    </p>
                  ) : null}
                  {row.themes.length > 0 ? (
                    <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-grey-blue">
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
                      (row.source === 'local' ? 'text-teal' : 'text-grey-blue')
                    }
                  >
                    {row.source}
                  </span>
                  <a
                    href={row.profile_url}
                    className="text-xs text-grey-blue underline-offset-4 hover:text-navy hover:underline"
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
              className="border border-rule bg-cream px-5 py-2 text-sm text-navy transition hover:bg-cream-dark disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          </div>
        ) : null}
      </section>
    </section>
  );
}