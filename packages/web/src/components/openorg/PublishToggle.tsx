/**
 * Draft/Published status badge + single Publish/Unpublish toggle button.
 *
 * Shared by EditProfile, EditStrategy, and EditIdea — they all share the
 * same published-or-draft model and the same UX affordance.
 *
 * The parent owns the mutation hooks and the error state; this file only
 * handles the visual primitives.
 */

interface PublishBadgeProps {
  published: boolean;
  noun?: string;
}

export function PublishBadge({ published, noun = 'Profile' }: PublishBadgeProps) {
  if (published) {
    return (
      <span
        aria-label={`${noun} is published`}
        className="inline-flex items-center gap-1.5 border border-emerald-700/40 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-emerald-900"
      >
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-700" />
        Published
      </span>
    );
  }
  return (
    <span
      aria-label={`${noun} is a draft`}
      className="inline-flex items-center gap-1.5 border border-rule bg-paper-2 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-muted"
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-muted/60" />
      Draft
    </span>
  );
}

interface PublishControlsProps {
  published: boolean;
  busy: boolean;
  onPublish: () => void;
  onUnpublish: () => void;
}

export function PublishControls({
  published,
  busy,
  onPublish,
  onUnpublish,
}: PublishControlsProps) {
  if (published) {
    return (
      <button
        type="button"
        onClick={onUnpublish}
        disabled={busy}
        aria-busy={busy}
        className="border border-ink/30 bg-paper px-4 py-1.5 text-sm font-medium text-ink transition hover:bg-paper-2 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy ? 'Unpublishing…' : 'Unpublish'}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onPublish}
      disabled={busy}
      aria-busy={busy}
      className="bg-ink px-4 py-1.5 text-sm font-medium text-paper transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {busy ? 'Publishing…' : 'Publish'}
    </button>
  );
}
