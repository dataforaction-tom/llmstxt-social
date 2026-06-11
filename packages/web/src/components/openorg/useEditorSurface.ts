import { useEffect, useState } from 'react';

export type EditorSurface = 'guided' | 'markdown';
export type RecordKind = 'profile' | 'strategy' | 'idea';

const KEY = (kind: RecordKind) => `openorg.editorSurface.${kind}`;

function readSurface(kind: RecordKind): EditorSurface {
  if (typeof window === 'undefined') return 'guided';
  const v = window.localStorage.getItem(KEY(kind));
  return v === 'markdown' ? 'markdown' : 'guided';
}

export function useEditorSurface(kind: RecordKind): [EditorSurface, (s: EditorSurface) => void] {
  const [surface, setSurface] = useState<EditorSurface>(() => readSurface(kind));
  useEffect(() => {
    setSurface(readSurface(kind));
  }, [kind]);
  const update = (s: EditorSurface) => {
    setSurface(s);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(KEY(kind), s);
    }
  };
  return [surface, update];
}
