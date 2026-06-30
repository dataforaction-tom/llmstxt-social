/**
 * Public profile detail page for an Open Org.
 *
 * Route: /openorg/:orgId
 * Spec section 4: "Profile detail view. Rendered view of the full profile —
 * not raw JSON." Displays mission, themes, programmes, beneficiaries,
 * evidence summary, strategies, ideas. Raw JSON URL is still available
 * via the "View raw" link for power users.
 */

import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPublicIdeas,
  fetchPublicOrgHistory,
  fetchPublicProfile,
  fetchPublicStrategies,
  fetchOrgSignals,
  useIdeaSignals,
  type PublicRecordSummary,
  type SignalOut,
} from '../../api/openorg';
import SignalButton from '../../components/openorg/SignalButton';
import {
  EvidenceItemCard,
  Section,
  StatusBadge,
  ThemeChips,
  TimelineSection,
  type EvidenceItem,
} from '../../components/openorg/detail';
import { formatDate } from '../../components/openorg/detailFormat';

interface Geography {
  primary_area?: string;
  primary_area_code?: string;
  operating_areas?: string[];
}

interface Contact {
  email?: string;
  phone?: string;
  address?: string;
}

interface Programme {
  name: string;
  description?: string;
  eligibility?: string;
  location?: string;
}

interface EvidenceSummary {
  beneficiaries_served_text?: string;
  outcomes?: string[];
}

interface Mission {
  summary?: string;
  themes?: string[];
  beneficiaries?: string[];
  theory_of_change?: string;
  programmes?: Programme[];
  evidence_summary?: EvidenceSummary;
  objects?: string;
}

interface Identity {
  name?: string;
  also_known_as?: string[];
  geography?: Geography;
  website?: string;
  contact?: Contact;
  founded?: string;
}

interface PublicProfile {
  identity?: Identity;
  mission?: Mission;
  evidence?: EvidenceItem[];
}

export default function ProfileDetailPage() {
  const { orgId: rawOrgId } = useParams<{ orgId: string }>();
  const orgId = rawOrgId ?? '';

  const profile = useQuery({
    queryKey: ['openorg', 'public-profile', orgId],
    queryFn: () => fetchPublicProfile(orgId) as Promise<PublicProfile>,
    enabled: Boolean(orgId),
    retry: false,
  });
  const strategies = useQuery({
    queryKey: ['openorg', 'public-strategies', orgId],
    queryFn: () => fetchPublicStrategies(orgId),
    enabled: Boolean(orgId),
    retry: false,
  });
  const ideas = useQuery({
    queryKey: ['openorg', 'public-ideas', orgId],
    queryFn: () => fetchPublicIdeas(orgId),
    enabled: Boolean(orgId),
    retry: false,
  });
  const history = useQuery({
    queryKey: ['openorg', 'public-history', orgId],
    queryFn: () => fetchPublicOrgHistory(orgId),
    enabled: Boolean(orgId),
    retry: false,
  });
  const signals = useQuery({
    queryKey: ['openorg', 'org-signals', orgId],
    queryFn: () => fetchOrgSignals(orgId),
    enabled: Boolean(orgId),
    retry: false,
  });

  if (!orgId) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="p-6 text-red-700">Missing org_id in URL.</div>
      </div>
    );
  }

  if (profile.isLoading) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10 text-grey-blue">Loading profile…</div>
      </div>
    );
  }
  if (profile.isError || !profile.data) {
    return (
      <div className="surface-cream min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="display-head text-2xl font-medium">Profile not found</h1>
          <p className="mt-3 text-sm text-grey-blue">
            <code className="font-mono">{orgId}</code> isn't a published Open Org profile.
            It may be unpublished, claimed but not yet generated, or a charity number we
            don't have in the index.
          </p>
          <p className="mt-6 text-sm">
            <Link to="/openorg/discover" className="underline">
              ← Back to discovery
            </Link>
          </p>
        </div>
      </div>
    );
  }

  const data = profile.data;
  const identity = data.identity ?? {};
  const mission = data.mission ?? {};
  const geography = identity.geography ?? {};
  const contact = identity.contact ?? {};
  const programmes = mission.programmes ?? [];
  const evidenceSummary = mission.evidence_summary ?? {};
  const evidenceItems = data.evidence ?? [];
  const themes = mission.themes ?? [];
  const beneficiaries = mission.beneficiaries ?? [];
  const aka = identity.also_known_as ?? [];
  const rawJsonUrl = `/open-org/${orgId}/profile.json`;

  return (
    <div className="surface-cream min-h-screen">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <nav className="mb-6 text-xs">
          <Link to="/openorg/discover" className="text-grey-blue hover:text-navy">
            ← Discover
          </Link>
        </nav>

        <header className="mb-8 border-b border-rule pb-6">
          <div className="kicker num">Organisation</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            {identity.name ?? orgId}
          </h1>
          {aka.length > 0 && (
            <p className="mt-1 text-sm text-grey-blue">
              Also known as: {aka.join(', ')}
            </p>
          )}
          <p className="mt-3 flex flex-wrap items-center gap-3 text-sm text-grey-blue">
            <code className="font-mono text-navy">{orgId}</code>
            {geography.primary_area && (
              <>
                <span className="text-rule">·</span>
                <span>{geography.primary_area}</span>
              </>
            )}
            {identity.website && (
              <>
                <span className="text-rule">·</span>
                <a
                  href={identity.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-navy"
                >
                  Website
                </a>
              </>
            )}
            <span className="text-rule">·</span>
            <a href={rawJsonUrl} className="underline hover:text-navy">
              View raw JSON
            </a>
          </p>
        </header>

        {mission.summary && (
          <Section title="Mission">
            <p className="text-lg leading-relaxed text-navy">{mission.summary}</p>
          </Section>
        )}

        {themes.length > 0 && (
          <Section title="Themes">
            <ThemeChips themes={themes} />
          </Section>
        )}

        {mission.theory_of_change && (
          <Section title="Theory of change">
            <p className="text-base leading-relaxed text-navy">{mission.theory_of_change}</p>
          </Section>
        )}

        {programmes.length > 0 && (
          <Section title="Programmes">
            <ul className="space-y-4">
              {programmes.map((p) => (
                <li key={p.name} className="border-l-2 border-rule pl-4">
                  <h3 className="font-medium text-navy">{p.name}</h3>
                  {p.description && (
                    <p className="mt-1 text-sm leading-relaxed text-navy/85">
                      {p.description}
                    </p>
                  )}
                  {(p.eligibility || p.location) && (
                    <p className="mt-1 text-xs text-grey-blue">
                      {p.eligibility && <>Eligibility: {p.eligibility}</>}
                      {p.eligibility && p.location && ' · '}
                      {p.location && <>Location: {p.location}</>}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {beneficiaries.length > 0 && (
          <Section title="Beneficiaries">
            <ul className="list-disc space-y-1 pl-5 text-sm text-navy">
              {beneficiaries.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </Section>
        )}

        {(evidenceSummary.beneficiaries_served_text || (evidenceSummary.outcomes?.length ?? 0) > 0) && (
          <Section title="Evidence summary">
            {evidenceSummary.beneficiaries_served_text && (
              <p className="text-sm text-navy">
                <span className="text-grey-blue">Reach:</span>{' '}
                {evidenceSummary.beneficiaries_served_text}
              </p>
            )}
            {evidenceSummary.outcomes && evidenceSummary.outcomes.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-navy">
                {evidenceSummary.outcomes.map((o, i) => (
                  <li key={i}>{o}</li>
                ))}
              </ul>
            )}
          </Section>
        )}

        {evidenceItems.length > 0 && (
          <Section title="Evidence">
            <ul className="space-y-6">
              {evidenceItems.map((item) => (
                <EvidenceItemCard key={item.evidence_id} item={item} />
              ))}
            </ul>
          </Section>
        )}

        {(strategies.data?.length ?? 0) > 0 && (
          <Section title="Strategies">
            <RecordList orgId={orgId} kind="strategies" items={strategies.data ?? []} />
          </Section>
        )}

        {(ideas.data?.length ?? 0) > 0 && (
          <Section title="Ideas">
            <RecordList orgId={orgId} kind="ideas" items={ideas.data ?? []} />
          </Section>
        )}

        {(contact.email || contact.phone || contact.address) && (
          <Section title="Contact">
            <dl className="grid gap-2 text-sm text-navy sm:grid-cols-[auto_1fr] sm:gap-x-4">
              {contact.email && (
                <>
                  <dt className="text-grey-blue">Email</dt>
                  <dd>
                    <a href={`mailto:${contact.email}`} className="underline">
                      {contact.email}
                    </a>
                  </dd>
                </>
              )}
              {contact.phone && (
                <>
                  <dt className="text-grey-blue">Phone</dt>
                  <dd>{contact.phone}</dd>
                </>
              )}
              {contact.address && (
                <>
                  <dt className="text-grey-blue">Address</dt>
                  <dd>{contact.address}</dd>
                </>
              )}
            </dl>
          </Section>
        )}

        <TimelineSection entries={history.data ?? []} />

        <FunderInterestSection
          orgId={orgId}
          ideas={ideas.data ?? []}
          signals={signals.data ?? []}
        />
      </div>
    </div>
  );
}

function RecordList({
  orgId,
  kind,
  items,
}: {
  orgId: string;
  kind: 'strategies' | 'ideas';
  items: PublicRecordSummary[];
}) {
  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const detailHref = `/openorg/${orgId}/${kind}/${item.slug}`;
        return (
          <li key={item.slug} className="border-l-2 border-rule pl-4">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h3 className="font-medium text-navy">
                <Link to={detailHref} className="hover:underline">
                  {item.slug}
                </Link>
              </h3>
              {item.status && (
                <StatusBadge kind={kind} status={item.status} />
              )}
            </div>
            {item.summary && (
              <p className="mt-1 text-sm leading-relaxed text-navy/85">{item.summary}</p>
            )}
            {item.themes.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {item.themes.map((t) => (
                  <span key={t} className="text-xs text-grey-blue">
                    #{t}
                  </span>
                ))}
              </div>
            )}
            {(item.created_at || item.updated_at) && (
              <p className="mt-1 text-xs text-grey-blue">
                {item.created_at && <>created {formatDate(item.created_at)}</>}
                {item.created_at && item.updated_at && ' · '}
                {item.updated_at && <>updated {formatDate(item.updated_at)}</>}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// --- funder interest (Phase 1 transparency) -------------------------------

function FunderInterestSection({
  orgId,
  ideas,
  signals,
}: {
  orgId: string;
  ideas: PublicRecordSummary[];
  signals: SignalOut[];
}) {
  if (ideas.length === 0 && signals.length === 0) return null;
  const total = signals.length;
  return (
    <Section title="Funder interest">
      <p className="text-sm text-grey-blue">
        {total === 0
          ? 'No funders have signalled interest yet — but they can.'
          : `${total} signal${total === 1 ? '' : 's'} of interest from funders.`}
      </p>
      {ideas.map((idea) => (
        <IdeaSignalRow key={idea.slug} orgId={orgId} slug={idea.slug} />
      ))}
    </Section>
  );
}

function IdeaSignalRow({ orgId, slug }: { orgId: string; slug: string }) {
  const { data } = useIdeaSignals(orgId, slug, true);
  const count = data?.length ?? 0;
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="mt-3 border-l-2 border-rule pl-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-medium text-navy">{slug}</h3>
        <span className="text-xs text-grey-blue">
          {count} signal{count === 1 ? '' : 's'}
        </span>
      </div>
      {expanded && (data?.length ?? 0) > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-navy">
          {data!.map((s) => (
            <li key={s.id}>
              <span className="font-medium">{s.funder_name ?? 'Anonymous'}</span>
              {s.message && <span className="text-grey-blue"> — {s.message}</span>}
            </li>
          ))}
        </ul>
      )}
      {count > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-grey-blue underline hover:text-navy"
        >
          {expanded ? 'Hide' : 'Show'} signals
        </button>
      )}
      <SignalButton orgId={orgId} slug={slug} />
    </div>
  );
}
