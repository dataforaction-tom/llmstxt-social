import { useEffect, useRef, useState } from 'react';
import type { GenerateStatusResponse } from '../../api/openorg';
import { t } from '../../microcopy';

interface GenerateLiveStatusProps {
  status: GenerateStatusResponse;
  onTimeout: () => void;
}

const FALLBACK_THRESHOLD_MS = 90_000;

function donePreview(payload: GenerateStatusResponse['payload']): string {
  if (!payload) return '';
  const parts: string[] = [];
  if (payload.programmes_count) parts.push(`${payload.programmes_count} programmes`);
  if (payload.themes_count) parts.push(`${payload.themes_count} themes`);
  if (payload.has_summary) parts.push('a strong mission statement');
  if (parts.length === 0) return '';
  return parts.join(', ');
}

export default function GenerateLiveStatus({ status, onTimeout }: GenerateLiveStatusProps) {
  const isTerminal = status.status === 'ready' || status.status === 'failed';
  // Server reports a long-running *generating* row via elapsed_ms.
  const serverTimedOut =
    status.status === 'generating' && status.elapsed_ms > FALLBACK_THRESHOLD_MS;
  // Backstop: a row stuck at 'pending' (task never picked up — worker down) has
  // elapsed_ms 0 forever, so the server check never fires. Time out from first
  // render instead, so the user isn't trapped on the spinner indefinitely.
  const [clientTimedOut, setClientTimedOut] = useState(false);
  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;

  useEffect(() => {
    if (serverTimedOut) onTimeoutRef.current();
  }, [serverTimedOut]);

  useEffect(() => {
    if (isTerminal) return;
    const timer = setTimeout(() => {
      setClientTimedOut(true);
      onTimeoutRef.current();
    }, FALLBACK_THRESHOLD_MS);
    return () => clearTimeout(timer);
  }, [isTerminal]);

  const timedOut = serverTimedOut || clientTimedOut;

  if (status.status === 'failed') {
    return (
      <div className="border-l-2 border-red-700/40 bg-red-50/40 px-4 py-3 text-sm text-red-900">
        Couldn't finish — please try again, or email us if it keeps failing.
      </div>
    );
  }

  if (status.status === 'ready') {
    const took = Math.max(1, Math.round(status.elapsed_ms / 1000));
    const preview = donePreview(status.payload);
    return (
      <div className="border-l-2 border-teal/40 bg-teal/10 px-4 py-3">
        <div className="kicker text-navy">✓ Draft ready</div>
        <p className="mt-1 text-sm text-navy">
          Took {took} seconds. {preview && <>{preview} found.</>}
        </p>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="border-l-2 border-rule bg-cream-dark px-4 py-3 text-sm text-navy">
        {t('generate.timeout')}
      </div>
    );
  }

  return (
    <div className="border-l-2 border-rule bg-cream-dark px-4 py-3 text-sm text-navy transition-opacity duration-200">
      {status.message ?? 'Working…'}
    </div>
  );
}
