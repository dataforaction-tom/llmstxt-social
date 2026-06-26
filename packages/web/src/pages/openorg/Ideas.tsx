/**
 * Open Org idea browser — cross-org list of published ideas.
 *
 * Spec section 4: "Idea browser. Secondary view of published ideas across
 * all organisations. Filterable by theme, place, status, cost range."
 *
 * Route: /openorg/ideas (public)
 */

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  fetchIdeasPage,
  useIdeasFirstPage,
  useThemes,
  useIdeaSignals,
  type IdeaFilters,
  type IdeaRow,
} from '../../api/openorg';

function IdeaInterestBadge({ orgId, slug }: { orgId: string; slug: string }) {
  const { data } = useIdeaSignals(orgId, slug, true);
  const count = data?.length ?? 0;
  if (count === 0) return null;
  return (
    <span
      className="rounded-full bg-teal/15 px-2 py-0.5 text-xs text-teal"
      title={`${count} funder signal${count === 1 ? '' : 's'} of interest`}
    >
      {count} interested
    </span>
  );
}

const STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  { value: 'seed', label: 'Seed' },
  { value: 'developing', label: 'Developing' },
  { value: 'active', label: 'Active' },
  { value: 'done', label: 'Done' },
];

export default function IdeasPage() {
  const themesQuery = useThemes();

  const [pendingFilters, setPendingFilters] = useState<IdeaFilters>({});
  const [appliedFilters, setAppliedFilters] = useState<IdeaFilters>({});
  const [moreRows, setMoreRows] = useState<IdeaRow[]>([]);
  const [moreCursor, setMoreCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const firstPage = useIdeasFirstPage(appliedFilters);

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    setMoreRows([]);
    setMoreCursor(null);
    setAppliedFilters(pendingFilters);
  };

  const handleReset = () => {
    setPendingFilters({});
    setAppliedFilters({});
    setMoreRows([]);
    setMoreCursor(null);
  };

  const handleLoadMore = async () => {
    const cursor = moreCursor ?? firstPage.data?.next_cursor ?? null;
    if (!cursor) return;
    setLoadingMore(true);
    try {
      const next = await fetchIdeasPage(appliedFilters, cursor);
      setMoreRows((current) => [...current, ...next.results]);
      setMoreCursor(next.next_cursor);
    } finally {
      setLoadingMore(false);
    }
  };

  const allRows = useMemo(() => {
    const base = firstPage.data?.results ?? [];
    return [...base, ...moreRows];
  }, [firstPage.data, moreRows]);

  const showLoadMore = Boolean(moreCursor ?? firstPage.data?.next_cursor);

  return (
    <div className="surface-cream min-h-screen">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <header className="mb-8 border-b border-rule pb-6">
          <div className="kicker num">Public</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Ideas
          </h1>
          <p className="mt-2 max-w-prose text-sm text-grey-blue">
            Specific proposals published by organisations across the Open Org
            network. Filter by theme, status, or cost range to find the work
            that connects to your priorities.
          </p>
          <p className="mt-3 text-xs">
            <Link to="/openorg/discover" className="underline text-grey-blue hover:text-navy">
              ← Browse organisations
            </Link>
          </p>
        </header>

        <form
          onSubmit={handleApply}
          className="mb-8 grid gap-4 border border-rule bg-cream-dark p-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          <label className="flex flex-col text-xs">
            <span className="kicker mb-1">Search</span>
            <input
              type="text"
              value={pendingFilters.q ?? ''}
              onChange={(e) =>
                setPendingFilters((f) => ({ ...f, q: e.target.value || undefined }))
              }
              placeholder="org name, idea name…"
              className="border border-rule bg-cream px-2 py-1 text-sm"
            />
          </label>

          <label className="flex flex-col text-xs">
            <span className="kicker mb-1">Theme</span>
            <select
              value={pendingFilters.theme ?? ''}
              onChange={(e) =>
                setPendingFilters((f) => ({
                  ...f,
                  theme: e.target.value || undefined,
                }))
              }
              className="border border-rule bg-cream px-2 py-1 text-sm"
            >
              <option value="">Any theme</option>
              {(themesQuery.data ?? []).map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-xs">
            <span className="kicker mb-1">Status</span>
            <select
              value={pendingFilters.status ?? ''}
              onChange={(e) =>
                setPendingFilters((f) => ({
                  ...f,
                  status: e.target.value || undefined,
                }))
              }
              className="border border-rule bg-cream px-2 py-1 text-sm"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-xs">
            <span className="kicker mb-1">Max indicative cost (£)</span>
            <input
              type="number"
              min={0}
              value={pendingFilters.costMax ?? ''}
              onChange={(e) =>
                setPendingFilters((f) => ({
                  ...f,
                  costMax: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
              placeholder="e.g. 100000"
              className="border border-rule bg-cream px-2 py-1 text-sm"
            />
          </label>

          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4">
            <button
              type="submit"
              className="bg-teal px-4 py-1.5 text-sm font-medium text-cream hover:bg-teal-light"
            >
              Apply
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="border border-rule px-4 py-1.5 text-sm text-navy hover:bg-cream-dark"
            >
              Reset
            </button>
          </div>
        </form>

        <section>
          <div className="kicker num mb-4">
            Ideas · {allRows.length}
            {showLoadMore ? '+' : ''}
          </div>

          {firstPage.isLoading ? (
            <div className="py-16 text-center text-grey-blue">Loading…</div>
          ) : firstPage.isError ? (
            <div className="py-16 text-center text-red-700">
              Couldn't load ideas. Please try again.
            </div>
          ) : allRows.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-display text-2xl text-navy">No matches.</p>
              <p className="mt-2 text-sm text-grey-blue">
                Try fewer filters, or widen the cost range.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-rule border-y border-rule">
              {allRows.map((row) => (
                <li key={`${row.org_id}-${row.slug}`} className="py-6">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <h2 className="display-head text-xl font-medium text-navy">
                      {row.slug}
                    </h2>
                    <div className="flex items-center gap-3">
                      {row.status && (
                        <span className="text-xs uppercase tracking-wider text-grey-blue">
                          {row.status}
                        </span>
                      )}
                      <IdeaInterestBadge orgId={row.org_id} slug={row.slug} />
                    </div>
                  </div>
                  <p className="mt-1 text-sm text-grey-blue">
                    <Link to={`/openorg/${row.org_id}`} className="hover:text-navy hover:underline">
                      {row.org_name}
                    </Link>
                    {row.primary_area ? ` · ${row.primary_area}` : ''}
                  </p>
                  {row.summary && (
                    <p className="mt-2 max-w-prose text-sm leading-relaxed text-navy/90">
                      {row.summary}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
                    {row.themes.slice(0, 6).map((t) => (
                      <span key={t} className="font-mono text-grey-blue">
                        #{t}
                      </span>
                    ))}
                    {(row.cost_lower || row.cost_upper) && (
                      <span className="text-grey-blue">
                        {row.cost_currency ?? 'GBP'}{' '}
                        {row.cost_lower?.toLocaleString() ?? '?'}–
                        {row.cost_upper?.toLocaleString() ?? '?'}
                      </span>
                    )}
                    <a
                      href={row.idea_url}
                      className="text-grey-blue underline-offset-4 hover:text-navy hover:underline"
                    >
                      idea.json →
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {showLoadMore && (
            <div className="py-6 text-center">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="border border-rule bg-cream px-4 py-1.5 text-sm hover:bg-cream-dark disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
