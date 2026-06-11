import { useCallback, useEffect, useRef, useState } from 'react';
import type { SaveState } from './SaveIndicator';

const DEBOUNCE_MS = 600;

export function useAutosave(source: string, save: (md: string) => Promise<unknown>) {
  const [state, setState] = useState<SaveState>('saved');
  const [savedAt, setSavedAt] = useState<Date | undefined>(undefined);
  const lastSavedRef = useRef<string>(source);
  const timerRef = useRef<number | null>(null);
  const pendingRef = useRef<string>(source);

  const doSave = useCallback(
    async (md: string) => {
      setState('saving');
      try {
        await save(md);
        lastSavedRef.current = md;
        setSavedAt(new Date());
        setState('saved');
      } catch {
        setState('error');
      }
    },
    [save],
  );

  useEffect(() => {
    pendingRef.current = source;
    if (source === lastSavedRef.current) {
      return undefined;
    }
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      void doSave(pendingRef.current);
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [source, doSave]);

  const retry = useCallback(() => {
    void doSave(pendingRef.current);
  }, [doSave]);

  return { state, savedAt, retry };
}
