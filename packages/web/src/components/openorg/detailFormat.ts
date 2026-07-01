/**
 * Formatting helpers for the public Open Org detail views.
 *
 * Kept in a non-component module so the component file (`detail.tsx`) only
 * exports components — required by the react-refresh lint rule.
 */

import type { PublicHistoryEntry } from '../../api/openorg';

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
