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

interface SurfaceSwitchProps {
  value: EditorSurface;
  onChange: (next: EditorSurface) => void;
}

export default function SurfaceSwitch({ value, onChange }: SurfaceSwitchProps) {
  return (
    <div role="group" aria-label="Editor surface" className="inline-flex border border-rule text-xs">
      <button
        type="button"
        onClick={() => onChange('guided')}
        aria-pressed={value === 'guided'}
        className={`px-3 py-1 uppercase tracking-wider transition ${
          value === 'guided' ? 'bg-ink text-paper' : 'bg-paper text-muted hover:text-ink'
        }`}
      >
        Guided
      </button>
      <button
        type="button"
        onClick={() => onChange('markdown')}
        aria-pressed={value === 'markdown'}
        className={`px-3 py-1 uppercase tracking-wider transition ${
          value === 'markdown' ? 'bg-ink text-paper' : 'bg-paper text-muted hover:text-ink'
        }`}
      >
        Markdown
      </button>
    </div>
  );
}
