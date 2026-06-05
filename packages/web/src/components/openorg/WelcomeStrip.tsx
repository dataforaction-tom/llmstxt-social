import { useState } from 'react';
import { t } from '../../microcopy';

interface WelcomeStripProps {
  orgId: string;
}

function key(orgId: string) {
  return `openorg.welcomeStrip.${orgId}`;
}

export default function WelcomeStrip({ orgId }: WelcomeStripProps) {
  const [shown, setShown] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(key(orgId)) === 'pending';
  });

  if (!shown) return null;

  const handleDismiss = () => {
    window.localStorage.setItem(key(orgId), 'dismissed');
    setShown(false);
  };

  return (
    <div className="border-l-2 border-ink bg-paper-2 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <p className="max-w-prose text-sm text-ink">{t('welcome.body')}</p>
        <button
          type="button"
          onClick={handleDismiss}
          className="border border-rule px-2 py-0.5 text-xs uppercase tracking-wider text-muted hover:text-ink"
        >
          {t('welcome.dismiss')}
        </button>
      </div>
    </div>
  );
}
