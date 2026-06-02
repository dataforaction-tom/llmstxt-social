import { useEffect, useState } from 'react';

export type SaveState = 'saved' | 'saving' | 'error' | 'unsaved';

interface SaveIndicatorProps {
  state: SaveState;
  savedAt?: Date;
  onRetry?: () => void;
}

function ageLabel(savedAt: Date, now: number): string {
  const diffSec = Math.max(0, Math.round((now - savedAt.getTime()) / 1000));
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  return `${Math.round(diffSec / 3600)}h ago`;
}

export default function SaveIndicator({ state, savedAt, onRetry }: SaveIndicatorProps) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (state !== 'saved') return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(id);
  }, [state]);

  if (state === 'saving') {
    return (
      <span className="kicker text-muted" aria-live="polite">
        Saving…
      </span>
    );
  }
  if (state === 'error') {
    return (
      <span className="kicker text-red-900" aria-live="assertive">
        Couldn't save —{' '}
        <button
          type="button"
          onClick={onRetry}
          className="ml-1 border border-rule px-2 py-0.5 text-xs hover:bg-paper-2"
        >
          Retry
        </button>
      </span>
    );
  }
  if (state === 'unsaved') {
    return (
      <span className="kicker text-muted" aria-live="polite">
        Unsaved · <span className="ml-1 font-mono">⌘S</span> to save
      </span>
    );
  }
  const age = savedAt ? ageLabel(savedAt, now) : 'just now';
  return (
    <span className="kicker text-muted" aria-live="polite">
      Saved · {age}
    </span>
  );
}
