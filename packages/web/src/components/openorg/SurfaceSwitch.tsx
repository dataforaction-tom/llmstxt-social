import type { EditorSurface } from './useEditorSurface';

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
