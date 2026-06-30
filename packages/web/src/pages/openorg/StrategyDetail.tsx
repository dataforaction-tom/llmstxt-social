/**
 * Public strategy detail page for an Open Org.
 *
 * Route: /openorg/:orgId/strategies/:slug
 * A rendered view of a published strategy — not raw JSON. Mirrors the
 * organisation profile page's editorial chrome and reuses the shared detail
 * components. The raw `.json` URL stays available via the "raw JSON" link.
 */

import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPublicStrategy,
  fetchPublicStrategyHistory,
} from '../../api/openorg';
import {
  Section,
  StatusBadge,
  ThemeChips,
  TimelineSection,
} from '../../components/openorg/detail';

interface Period {
  start?: string;
  end?: string;
  horizon?: string;
}

interface Priority {
  title: string;
  themes?: string[];
  maturity?: string;
  narrative?: string;
  success_indicators?: string[];
  dependencies?: string[];
}

interface NotDoing {
  title: string;
  rationale?: string;
}

interface Tension {
  title: string;
  narrative?: string;
}

interface Relationships {
  partnerships?: string;
  ecosystem_position?: string;
  community_mandate?: string;
}

interface ResourceModel {
  current_funding_mix?: string;
  sustainability_direction?: string;
  resourcing_gaps?: string;
}

interface PublicStrategy {
  title?: string;
  status?: string;
  access_level?: string;
  period?: Period;
  themes?: string[];
  summary?: string;
  priorities?: Priority[];
  not_doing?: NotDoing[];
  tensions?: Tension[];
  learning?: { what_changed?: string };
  relationships?: Relationships;
  resource_model?: ResourceModel;
}

export default function StrategyDetailPage() {
  const { orgId: rawOrgId, slug: rawSlug } = useParams<{
    orgId: string;
    slug: string;
  }>();
  const orgId = rawOrgId ?? '';
  const slug = rawSlug ?? '';

  const strategy = useQuery({
    queryKey: ['openorg', 'public-strategy', orgId, slug],
    queryFn: () => fetchPublicStrategy(orgId, slug) as Promise<PublicStrategy>,
    enabled: Boolean(orgId && slug),
    retry: false,
  });
  const history = useQuery({
    queryKey: ['openorg', 'public-strategy-history', orgId, slug],
    queryFn: () => fetchPublicStrategyHistory(orgId, slug),
    enabled: Boolean(orgId && slug),
    retry: false,
  });

  if (strategy.isLoading) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10 text-grey-blue">
          Loading strategy…
        </div>
      </div>
    );
  }
  if (strategy.isError || !strategy.data) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="display-head text-2xl font-medium">Strategy not found</h1>
          <p className="mt-3 text-sm text-grey-blue">
            <code className="font-mono">{slug}</code> isn't a published strategy for{' '}
            <code className="font-mono">{orgId}</code>.
          </p>
          <p className="mt-6 text-sm">
            <Link to={`/openorg/${orgId}`} className="underline">
              ← Back to organisation
            </Link>
          </p>
        </div>
      </div>
    );
  }

  const data = strategy.data;
  const themes = data.themes ?? [];
  const priorities = data.priorities ?? [];
  const notDoing = data.not_doing ?? [];
  const tensions = data.tensions ?? [];
  const period = data.period ?? {};
  const periodLabel = [period.start, period.end].filter(Boolean).join('–');
  const rawJsonUrl = `/open-org/${orgId}/strategies/${slug}.json`;

  return (
    <div className="surface-cream min-h-screen">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <nav className="mb-6 text-xs">
          <Link to={`/openorg/${orgId}`} className="text-grey-blue hover:text-navy">
            ← {orgId}
          </Link>
        </nav>

        <header className="mb-8 border-b border-rule pb-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className="kicker num">Strategy</div>
            {data.status && <StatusBadge kind="strategies" status={data.status} />}
          </div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            {data.title ?? slug}
          </h1>
          <p className="mt-3 flex flex-wrap items-center gap-3 text-sm text-grey-blue">
            {periodLabel && <span>{periodLabel}</span>}
            {period.horizon && <span>· {period.horizon} horizon</span>}
            <span className="text-rule">·</span>
            <a href={rawJsonUrl} className="underline hover:text-navy">
              View raw JSON
            </a>
          </p>
        </header>

        {data.summary && (
          <Section title="Summary">
            <p className="text-lg leading-relaxed text-navy">{data.summary}</p>
          </Section>
        )}

        {themes.length > 0 && (
          <Section title="Themes">
            <ThemeChips themes={themes} />
          </Section>
        )}

        {priorities.length > 0 && (
          <Section title="Priorities">
            <ul className="space-y-5">
              {priorities.map((p, i) => (
                <li key={i} className="border-l-2 border-teal/50 pl-4">
                  <div className="flex flex-wrap items-baseline gap-x-3">
                    <h3 className="font-medium text-navy">{p.title}</h3>
                    {p.maturity && (
                      <span className="text-xs uppercase tracking-wider text-grey-blue">
                        {p.maturity}
                      </span>
                    )}
                  </div>
                  {p.narrative && (
                    <p className="mt-1 text-sm leading-relaxed text-navy/85">
                      {p.narrative}
                    </p>
                  )}
                  {(p.success_indicators?.length ?? 0) > 0 && (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-navy">
                      {p.success_indicators!.map((s, j) => (
                        <li key={j}>{s}</li>
                      ))}
                    </ul>
                  )}
                  {(p.dependencies?.length ?? 0) > 0 && (
                    <p className="mt-1 text-xs text-grey-blue">
                      Depends on: {p.dependencies!.join(', ')}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {notDoing.length > 0 && (
          <Section title="Not doing">
            <ul className="space-y-3">
              {notDoing.map((n, i) => (
                <li key={i} className="border-l-2 border-coral/50 pl-4">
                  <h3 className="font-medium text-navy">{n.title}</h3>
                  {n.rationale && (
                    <p className="mt-1 text-sm leading-relaxed text-navy/85">
                      {n.rationale}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {tensions.length > 0 && (
          <Section title="Tensions">
            <ul className="space-y-3">
              {tensions.map((t, i) => (
                <li key={i} className="border-l-2 border-amber/50 pl-4">
                  <h3 className="font-medium text-navy">{t.title}</h3>
                  {t.narrative && (
                    <p className="mt-1 text-sm leading-relaxed text-navy/85">
                      {t.narrative}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {data.learning?.what_changed && (
          <Section title="Learning">
            <p className="text-base leading-relaxed text-navy">
              {data.learning.what_changed}
            </p>
          </Section>
        )}

        {data.relationships && <RelationshipsSection rel={data.relationships} />}
        {data.resource_model && <ResourceSection rm={data.resource_model} />}

        <TimelineSection entries={history.data ?? []} />
      </div>
    </div>
  );
}

function DefinitionRows({ rows }: { rows: [string, string | undefined][] }) {
  const present = rows.filter(([, v]) => Boolean(v));
  if (present.length === 0) return null;
  return (
    <dl className="grid gap-2 text-sm text-navy sm:grid-cols-[auto_1fr] sm:gap-x-4">
      {present.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-grey-blue">{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RelationshipsSection({ rel }: { rel: Relationships }) {
  const rows: [string, string | undefined][] = [
    ['Partnerships', rel.partnerships],
    ['Ecosystem position', rel.ecosystem_position],
    ['Community mandate', rel.community_mandate],
  ];
  if (rows.every(([, v]) => !v)) return null;
  return (
    <Section title="Relationships">
      <DefinitionRows rows={rows} />
    </Section>
  );
}

function ResourceSection({ rm }: { rm: ResourceModel }) {
  const rows: [string, string | undefined][] = [
    ['Funding mix', rm.current_funding_mix],
    ['Sustainability', rm.sustainability_direction],
    ['Resourcing gaps', rm.resourcing_gaps],
  ];
  if (rows.every(([, v]) => !v)) return null;
  return (
    <Section title="Resource model">
      <DefinitionRows rows={rows} />
    </Section>
  );
}
