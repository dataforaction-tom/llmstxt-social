/**
 * Shared presentational building blocks for the public Open Org detail views
 * (organisation profile, idea, strategy).
 *
 * These were originally local to ProfileDetail.tsx; they're extracted here so
 * the idea and strategy detail pages render with identical chrome and styling
 * without duplicating markup. Pure presentation — no data fetching.
 */

import type { ReactNode } from 'react';
import type { PublicHistoryEntry } from '../../api/openorg';

// --- section wrapper -------------------------------------------------------

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <div className="kicker mb-3">{title}</div>
      {children}
    </section>
  );
}

// --- theme chips -----------------------------------------------------------

/** Bordered theme chips (matches the profile "Themes" section). */
export function ThemeChips({ themes }: { themes: string[] }) {
  if (themes.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {themes.map((t) => (
        <span
          key={t}
          className="border border-rule bg-cream-dark px-2 py-0.5 text-xs text-navy"
        >
          {t}
        </span>
      ))}
    </div>
  );
}

// --- status badges ---------------------------------------------------------

const IDEA_STATUS_CLASSES: Record<string, string> = {
  seed: 'bg-grey-blue/15 text-grey-blue',
  developing: 'bg-teal/15 text-teal',
  shaped: 'bg-amber/15 text-amber',
  delivered: 'bg-teal/20 text-teal',
  archived: 'bg-grey-blue/10 text-grey-blue/70',
};

const STRATEGY_STATUS_CLASSES: Record<string, string> = {
  draft: 'bg-grey-blue/15 text-grey-blue',
  active: 'bg-teal/15 text-teal',
  archived: 'bg-grey-blue/10 text-grey-blue/70',
};

export function StatusBadge({
  kind,
  status,
}: {
  kind: 'strategies' | 'ideas';
  status: string;
}) {
  const palette = kind === 'ideas' ? IDEA_STATUS_CLASSES : STRATEGY_STATUS_CLASSES;
  const className = palette[status] ?? 'bg-grey-blue/15 text-grey-blue';
  return (
    <span
      className={`rounded-brand px-2 py-0.5 text-xs uppercase tracking-wider ${className}`}
    >
      {status}
    </span>
  );
}

// --- evidence --------------------------------------------------------------

export interface EvidenceItem {
  evidence_id: string;
  title: string;
  description?: string;
  evidence_type?: string;
  date?: string;
  url?: string;
  themes?: string[];
  outcomes?: string[];
}

const EVIDENCE_TYPE_CLASSES: Record<string, string> = {
  evaluation: 'bg-teal/15 text-teal',
  outcome_data: 'bg-amber/15 text-amber',
  annual_report: 'bg-navy/15 text-navy',
  case_study: 'bg-coral/15 text-coral',
  learning_reflection: 'bg-grey-blue/15 text-grey-blue',
  external_research: 'bg-teal/10 text-teal',
  other: 'bg-grey-blue/10 text-grey-blue',
};

export function EvidenceTypeBadge({ type }: { type: string }) {
  const className = EVIDENCE_TYPE_CLASSES[type] ?? 'bg-grey-blue/10 text-grey-blue';
  return (
    <span
      className={`rounded-brand px-2 py-0.5 text-xs uppercase tracking-wider ${className}`}
      data-testid="evidence-type-badge"
    >
      {type}
    </span>
  );
}

export function EvidenceItemCard({ item }: { item: EvidenceItem }) {
  const themes = item.themes ?? [];
  const outcomes = item.outcomes ?? [];
  return (
    <li className="border-l-2 border-rule pl-4">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h3 className="font-medium text-navy">{item.title}</h3>
        {item.evidence_type && <EvidenceTypeBadge type={item.evidence_type} />}
      </div>
      {item.date && <p className="mt-0.5 text-xs text-grey-blue">{item.date}</p>}
      {item.description && (
        <p className="mt-1 text-sm leading-relaxed text-navy/85">{item.description}</p>
      )}
      {themes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {themes.map((t) => (
            <span
              key={t}
              className="border border-rule bg-cream-dark px-2 py-0.5 text-xs text-navy"
            >
              {t}
            </span>
          ))}
        </div>
      )}
      {outcomes.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-navy">
          {outcomes.map((o, i) => (
            <li key={i}>{o}</li>
          ))}
        </ul>
      )}
      {item.url && (
        <p className="mt-2 text-sm">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-navy"
          >
            View evidence →
          </a>
        </p>
      )}
    </li>
  );
}

// --- timeline --------------------------------------------------------------

export function TimelineSection({ entries }: { entries: PublicHistoryEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <Section title="Timeline">
      <ol className="relative border-l-2 border-teal/40 pl-6">
        {entries.map((entry, i) => (
          <li key={`${entry.timestamp}-${i}`} className="mb-5 last:mb-0">
            <span
              className="absolute -left-[7px] mt-1 h-3 w-3 rounded-full bg-navy"
              aria-hidden
            />
            <div className="text-xs uppercase tracking-wider text-grey-blue">
              {historyLabel(entry)}
            </div>
            <div className="mt-0.5 text-sm text-navy">{entry.summary}</div>
            <time className="mt-0.5 block text-xs text-grey-blue">
              {formatDate(entry.timestamp)}
            </time>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export function historyLabel(entry: PublicHistoryEntry): string {
  if (entry.summary.toLowerCase().includes('status changed')) {
    return `${entry.parent_kind.charAt(0).toUpperCase()}${entry.parent_kind.slice(1)} status changed`;
  }
  if (entry.parent_kind === 'profile') return 'Profile updated';
  if (entry.parent_kind === 'strategy') return 'Strategy published';
  if (entry.parent_kind === 'idea') return 'Idea updated';
  return 'Updated';
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
