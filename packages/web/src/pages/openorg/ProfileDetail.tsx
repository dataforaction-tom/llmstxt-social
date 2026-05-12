/**
 * Public profile detail page for an Open Org.
 *
 * Route: /openorg/:orgId
 * Spec section 4: "Profile detail view. Rendered view of the full profile —
 * not raw JSON." Displays mission, themes, programmes, beneficiaries,
 * evidence summary, strategies, ideas. Raw JSON URL is still available
 * via the "View raw" link for power users.
 */

import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  fetchPublicIdeas,
  fetchPublicProfile,
  fetchPublicStrategies,
  type PublicRecordSummary,
} from '../../api/openorg';

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

  if (!orgId) {
    return <div className="p-6 text-red-700">Missing org_id in URL.</div>;
  }

  if (profile.isLoading) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10 text-muted">Loading profile…</div>
      </div>
    );
  }
  if (profile.isError || !profile.data) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="display-head text-2xl font-medium">Profile not found</h1>
          <p className="mt-3 text-sm text-muted">
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
  const evidence = mission.evidence_summary ?? {};
  const themes = mission.themes ?? [];
  const beneficiaries = mission.beneficiaries ?? [];
  const aka = identity.also_known_as ?? [];
  const rawJsonUrl = `/open-org/${orgId}/profile.json`;

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <nav className="mb-6 text-xs">
          <Link to="/openorg/discover" className="text-muted hover:text-ink">
            ← Discover
          </Link>
        </nav>

        <header className="mb-8 border-b border-rule pb-6">
          <div className="kicker num">Organisation</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            {identity.name ?? orgId}
          </h1>
          {aka.length > 0 && (
            <p className="mt-1 text-sm text-muted">
              Also known as: {aka.join(', ')}
            </p>
          )}
          <p className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
            <code className="font-mono text-ink">{orgId}</code>
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
                  className="underline hover:text-ink"
                >
                  Website
                </a>
              </>
            )}
            <span className="text-rule">·</span>
            <a href={rawJsonUrl} className="underline hover:text-ink">
              View raw JSON
            </a>
          </p>
        </header>

        {mission.summary && (
          <Section title="Mission">
            <p className="text-lg leading-relaxed text-ink">{mission.summary}</p>
          </Section>
        )}

        {themes.length > 0 && (
          <Section title="Themes">
            <div className="flex flex-wrap gap-2">
              {themes.map((t) => (
                <span
                  key={t}
                  className="border border-rule bg-paper-2 px-2 py-0.5 text-xs text-ink"
                >
                  {t}
                </span>
              ))}
            </div>
          </Section>
        )}

        {mission.theory_of_change && (
          <Section title="Theory of change">
            <p className="text-base leading-relaxed text-ink">{mission.theory_of_change}</p>
          </Section>
        )}

        {programmes.length > 0 && (
          <Section title="Programmes">
            <ul className="space-y-4">
              {programmes.map((p) => (
                <li key={p.name} className="border-l-2 border-rule pl-4">
                  <h3 className="font-medium text-ink">{p.name}</h3>
                  {p.description && (
                    <p className="mt-1 text-sm leading-relaxed text-ink/85">
                      {p.description}
                    </p>
                  )}
                  {(p.eligibility || p.location) && (
                    <p className="mt-1 text-xs text-muted">
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
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
              {beneficiaries.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </Section>
        )}

        {(evidence.beneficiaries_served_text || (evidence.outcomes?.length ?? 0) > 0) && (
          <Section title="Evidence">
            {evidence.beneficiaries_served_text && (
              <p className="text-sm text-ink">
                <span className="text-muted">Reach:</span>{' '}
                {evidence.beneficiaries_served_text}
              </p>
            )}
            {evidence.outcomes && evidence.outcomes.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
                {evidence.outcomes.map((o, i) => (
                  <li key={i}>{o}</li>
                ))}
              </ul>
            )}
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
            <dl className="grid gap-2 text-sm text-ink sm:grid-cols-[auto_1fr] sm:gap-x-4">
              {contact.email && (
                <>
                  <dt className="text-muted">Email</dt>
                  <dd>
                    <a href={`mailto:${contact.email}`} className="underline">
                      {contact.email}
                    </a>
                  </dd>
                </>
              )}
              {contact.phone && (
                <>
                  <dt className="text-muted">Phone</dt>
                  <dd>{contact.phone}</dd>
                </>
              )}
              {contact.address && (
                <>
                  <dt className="text-muted">Address</dt>
                  <dd>{contact.address}</dd>
                </>
              )}
            </dl>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <div className="kicker mb-3">{title}</div>
      {children}
    </section>
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
        const jsonHref = `/open-org/${orgId}/${kind}/${item.slug}.json`;
        return (
          <li key={item.slug} className="border-l-2 border-rule pl-4">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h3 className="font-medium text-ink">
                <a href={jsonHref} className="hover:underline">
                  {item.slug}
                </a>
              </h3>
              {item.status && (
                <span className="text-xs uppercase tracking-wider text-muted">
                  {item.status}
                </span>
              )}
            </div>
            {item.summary && (
              <p className="mt-1 text-sm leading-relaxed text-ink/85">{item.summary}</p>
            )}
            {item.themes.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {item.themes.map((t) => (
                  <span key={t} className="text-xs text-muted">
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
