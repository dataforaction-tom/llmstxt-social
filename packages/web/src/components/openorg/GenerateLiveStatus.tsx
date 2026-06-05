import { useEffect } from 'react';
import type { GenerateStatusResponse } from '../../api/openorg';

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
  const timedOut = status.status === 'generating' && status.elapsed_ms > FALLBACK_THRESHOLD_MS;

  useEffect(() => {
    if (timedOut) onTimeout();
  }, [timedOut, onTimeout]);

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
      <div className="border-l-2 border-emerald-700/40 bg-emerald-50/40 px-4 py-3">
        <div className="kicker text-emerald-900">✓ Draft ready</div>
        <p className="mt-1 text-sm text-ink">
          Took {took} seconds. {preview && <>{preview} found.</>}
        </p>
      </div>
    );
  }

  if (timedOut) {
    return (
      <div className="border-l-2 border-rule bg-paper-2 px-4 py-3 text-sm text-ink">
        Still working in the background — we'll email you when it's ready, feel
        free to close this tab.
      </div>
    );
  }

  return (
    <div className="border-l-2 border-rule bg-paper-2 px-4 py-3 text-sm text-ink transition-opacity duration-200">
      {status.message ?? 'Working…'}
    </div>
  );
}
