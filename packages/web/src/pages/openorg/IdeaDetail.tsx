/**
 * Public idea detail page for an Open Org.
 *
 * Route: /openorg/:orgId/ideas/:slug
 * A rendered view of a published idea — not raw JSON. Mirrors the
 * organisation profile page's editorial chrome and reuses the shared detail
 * components. The raw `.json` URL stays available via the "raw JSON" link.
 */

import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPublicIdea,
  fetchPublicIdeaHistory,
  useIdeaSignals,
} from '../../api/openorg';
import SignalButton from '../../components/openorg/SignalButton';
import {
  Section,
  StatusBadge,
  ThemeChips,
  TimelineSection,
} from '../../components/openorg/detail';

interface IndicativeCost {
  lower?: number;
  upper?: number;
  currency?: string;
  period?: string;
}

interface Place {
  description?: string;
  area_codes?: string[];
}

interface EvidenceRef {
  evidence_id: string;
  relevance?: string;
}

interface Connection {
  org_name?: string;
  org_id?: string;
  relationship?: string;
  mutual?: boolean;
}

interface Collaborator {
  org_name?: string;
  org_id?: string;
  role?: string;
  confirmed?: boolean;
}

interface PublicIdea {
  title?: string;
  status?: string;
  summary?: string;
  detail?: string;
  place?: Place;
  themes?: string[];
  beneficiaries?: string[];
  indicative_cost?: IndicativeCost;
  evidence_base?: EvidenceRef[];
  connections?: Connection[];
  collaborators?: Collaborator[];
  linked_strategy_id?: string;
}

export default function IdeaDetailPage() {
  const { orgId: rawOrgId, slug: rawSlug } = useParams<{
    orgId: string;
    slug: string;
  }>();
  const orgId = rawOrgId ?? '';
  const slug = rawSlug ?? '';

  const idea = useQuery({
    queryKey: ['openorg', 'public-idea', orgId, slug],
    queryFn: () => fetchPublicIdea(orgId, slug) as Promise<PublicIdea>,
    enabled: Boolean(orgId && slug),
    retry: false,
  });
  const history = useQuery({
    queryKey: ['openorg', 'public-idea-history', orgId, slug],
    queryFn: () => fetchPublicIdeaHistory(orgId, slug),
    enabled: Boolean(orgId && slug),
    retry: false,
  });
  const { data: signals } = useIdeaSignals(orgId, slug, Boolean(orgId && slug));

  if (idea.isLoading) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10 text-grey-blue">Loading idea…</div>
      </div>
    );
  }
  if (idea.isError || !idea.data) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="display-head text-2xl font-medium">Idea not found</h1>
          <p className="mt-3 text-sm text-grey-blue">
            <code className="font-mono">{slug}</code> isn't a published idea for{' '}
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

  const data = idea.data;
  const themes = data.themes ?? [];
  const beneficiaries = data.beneficiaries ?? [];
  const collaborators = data.collaborators ?? [];
  const connections = data.connections ?? [];
  const evidenceBase = data.evidence_base ?? [];
  const signalCount = signals?.length ?? 0;
  const rawJsonUrl = `/open-org/${orgId}/ideas/${slug}.json`;

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
            <div className="kicker num">Idea</div>
            {data.status && <StatusBadge kind="ideas" status={data.status} />}
          </div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            {data.title ?? slug}
          </h1>
          <p className="mt-3 flex flex-wrap items-center gap-3 text-sm text-grey-blue">
            {data.place?.description && <span>{data.place.description}</span>}
            {data.place?.description && <span className="text-rule">·</span>}
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

        {data.detail && (
          <Section title="Detail">
            <p className="whitespace-pre-line text-base leading-relaxed text-navy">
              {data.detail}
            </p>
          </Section>
        )}

        {themes.length > 0 && (
          <Section title="Themes">
            <ThemeChips themes={themes} />
          </Section>
        )}

        {data.indicative_cost && <CostSection cost={data.indicative_cost} />}

        {beneficiaries.length > 0 && (
          <Section title="Beneficiaries">
            <ul className="list-disc space-y-1 pl-5 text-sm text-navy">
              {beneficiaries.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </Section>
        )}

        {collaborators.length > 0 && (
          <Section title="Collaborators">
            <ul className="space-y-2">
              {collaborators.map((c, i) => (
                <li key={i} className="border-l-2 border-rule pl-4 text-sm">
                  <span className="font-medium text-navy">
                    {c.org_id ? (
                      <Link to={`/openorg/${c.org_id}`} className="hover:underline">
                        {c.org_name ?? c.org_id}
                      </Link>
                    ) : (
                      (c.org_name ?? 'Unnamed')
                    )}
                  </span>
                  {c.role && <span className="text-grey-blue"> — {c.role}</span>}
                  {c.confirmed === false && (
                    <span className="ml-2 text-xs text-grey-blue">(unconfirmed)</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {connections.length > 0 && (
          <Section title="Connections">
            <ul className="space-y-2">
              {connections.map((c, i) => (
                <li key={i} className="border-l-2 border-rule pl-4 text-sm">
                  <span className="font-medium text-navy">
                    {c.org_id ? (
                      <Link to={`/openorg/${c.org_id}`} className="hover:underline">
                        {c.org_name ?? c.org_id}
                      </Link>
                    ) : (
                      (c.org_name ?? 'Unnamed')
                    )}
                  </span>
                  {c.relationship && (
                    <span className="text-grey-blue"> — {c.relationship}</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {evidenceBase.length > 0 && (
          <Section title="Evidence base">
            <ul className="space-y-2">
              {evidenceBase.map((e, i) => (
                <li key={i} className="border-l-2 border-rule pl-4 text-sm">
                  <span className="font-mono text-xs text-grey-blue">{e.evidence_id}</span>
                  {e.relevance && (
                    <p className="mt-0.5 text-navy/85">{e.relevance}</p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {data.linked_strategy_id && (
          <Section title="Linked strategy">
            <Link
              to={`/openorg/${orgId}/strategies/${data.linked_strategy_id}`}
              className="text-sm text-navy underline hover:text-teal"
            >
              {data.linked_strategy_id}
            </Link>
          </Section>
        )}

        <Section title="Funder interest">
          <p className="text-sm text-grey-blue">
            {signalCount === 0
              ? 'No funders have signalled interest yet — but they can.'
              : `${signalCount} signal${signalCount === 1 ? '' : 's'} of interest.`}
          </p>
          <SignalButton orgId={orgId} slug={slug} />
        </Section>

        <TimelineSection entries={history.data ?? []} />
      </div>
    </div>
  );
}

function CostSection({ cost }: { cost: IndicativeCost }) {
  const { lower, upper, currency, period } = cost;
  if (lower == null && upper == null) return null;
  const fmt = (n: number) =>
    new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: currency || 'GBP',
      maximumFractionDigits: 0,
    }).format(n);
  let range: string;
  if (lower != null && upper != null) range = `${fmt(lower)}–${fmt(upper)}`;
  else range = fmt((lower ?? upper) as number);
  return (
    <Section title="Indicative cost">
      <p className="text-base text-navy">
        {range}
        {period && <span className="text-grey-blue"> / {period}</span>}
      </p>
    </Section>
  );
}
