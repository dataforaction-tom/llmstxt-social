import { useEffect, useState } from 'react';
import { PublishBadge } from './PublishToggle';
import { t } from '../../microcopy';

interface PublishStripProps {
  published: boolean;
  busy: boolean;
  onPublish: () => void;
  onUnpublish: () => void;
  liveUrl: string;
  /** Set when a publish just succeeded — drives the celebratory state for 8s. */
  justPublishedAt?: Date;
  noun?: string;
}

export default function PublishStrip({
  published,
  busy,
  onPublish,
  onUnpublish,
  liveUrl,
  justPublishedAt,
  noun = 'profile',
}: PublishStripProps) {
  const [confirming, setConfirming] = useState<null | 'publish' | 'unpublish'>(null);
  const [celebrating, setCelebrating] = useState<boolean>(Boolean(justPublishedAt));
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!justPublishedAt) return undefined;
    setCelebrating(true);
    const id = window.setTimeout(() => setCelebrating(false), 8_000);
    return () => window.clearTimeout(id);
  }, [justPublishedAt]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(liveUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_500);
    } catch {
      // Clipboard blocked — leave it; the link is still selectable on the page.
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <PublishBadge published={published} noun={noun.charAt(0).toUpperCase() + noun.slice(1)} />
        {confirming === null && !published && (
          <button
            type="button"
            onClick={() => setConfirming('publish')}
            disabled={busy}
            className="bg-teal px-4 py-1.5 text-sm font-medium text-cream hover:bg-teal-light disabled:opacity-40"
          >
            Publish
          </button>
        )}
        {confirming === null && published && !celebrating && (
          <button
            type="button"
            onClick={() => setConfirming('unpublish')}
            disabled={busy}
            className="border border-navy/30 bg-cream px-4 py-1.5 text-sm font-medium text-navy hover:bg-cream-dark disabled:opacity-40"
          >
            Unpublish
          </button>
        )}
      </div>

      {confirming === 'publish' && (
        <div role="region" aria-live="polite" className="border-l-2 border-navy bg-cream-dark px-4 py-3 text-sm">
          <p>{t('publish.confirm.prompt', { noun, url: liveUrl })}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setConfirming(null);
                onPublish();
              }}
              disabled={busy}
              className="bg-teal px-3 py-1 text-xs uppercase tracking-wider text-cream disabled:opacity-40"
            >
              {t('publish.confirm.publish')}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="border border-rule px-3 py-1 text-xs uppercase tracking-wider text-grey-blue hover:text-navy"
            >
              {t('publish.confirm.notyet')}
            </button>
          </div>
        </div>
      )}

      {confirming === 'unpublish' && (
        <div role="region" aria-live="polite" className="border-l-2 border-navy bg-cream-dark px-4 py-3 text-sm">
          <p>Unpublish this {noun}? It will be removed from the federated network.</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setConfirming(null);
                onUnpublish();
              }}
              disabled={busy}
              className="border border-navy/30 bg-cream px-3 py-1 text-xs uppercase tracking-wider text-navy disabled:opacity-40"
            >
              Unpublish
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="border border-rule px-3 py-1 text-xs uppercase tracking-wider text-grey-blue hover:text-navy"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {celebrating && (
        <div className="flex flex-col gap-1">
          <div
            aria-hidden
            className="h-px w-full origin-left bg-amber transition-transform duration-[600ms] ease-out"
            style={{ transform: 'scaleX(1)' }}
          />
          <p className="text-sm text-navy">
            Live at <code className="font-mono">{liveUrl}</code> ·{' '}
            <button
              type="button"
              onClick={handleCopy}
              className="underline decoration-rule underline-offset-2 hover:text-teal"
            >
              {t('publish.celebrate.share')}
            </button>
            {copied && (
              <span className="ml-2 text-xs text-teal">{t('publish.celebrate.copied')}</span>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
