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
        className="inline-flex items-center gap-1.5 border border-teal/40 bg-teal/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-navy"
      >
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-teal" />
        Published
      </span>
    );
  }
  return (
    <span
      aria-label={`${noun} is a draft`}
      className="inline-flex items-center gap-1.5 border border-rule bg-cream-dark px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-grey-blue"
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-grey-blue/60" />
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
        className="border border-navy/30 bg-cream px-4 py-1.5 text-sm font-medium text-navy transition hover:bg-cream-dark disabled:cursor-not-allowed disabled:opacity-40"
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
      className="bg-teal px-4 py-1.5 text-sm font-medium text-cream transition hover:bg-teal-light disabled:cursor-not-allowed disabled:opacity-40"
    >
      {busy ? 'Publishing…' : 'Publish'}
    </button>
  );
}
