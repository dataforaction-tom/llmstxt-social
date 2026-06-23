import { useEffect, useState } from 'react';
import MarkdownEditor from './MarkdownEditor';
import GuidedEditor from './guided/GuidedEditor';
import SurfaceSwitch from './SurfaceSwitch';
import { useEditorSurface, type RecordKind } from './useEditorSurface';
import SaveIndicator from './SaveIndicator';
import { useAutosave } from './useAutosave';
import type { GuidedSection } from './guided/sections/profile';
import type { PillOption } from './guided/fields/PillPicker';
import type { ValidationFieldError } from '../../api/openorg';

interface EditorShellProps {
  kind: RecordKind;
  initialSource: string;
  sections: GuidedSection[];
  onSave: (markdown: string) => Promise<unknown>;
  vocabs: Record<string, PillOption[]>;
  saving?: boolean;
  validationErrors?: ValidationFieldError[];
  saveLabel?: string;
  startHereId?: string;
}

export default function EditorShell({
  kind,
  initialSource,
  sections,
  onSave,
  vocabs,
  saving = false,
  validationErrors = [],
  saveLabel = 'Save',
  startHereId,
}: EditorShellProps) {
  const [surface, setSurface] = useEditorSurface(kind);
  const [source, setSource] = useState(initialSource);

  useEffect(() => {
    setSource(initialSource);
  }, [initialSource]);

  // Only autosave on the guided surface; markdown surface uses explicit Save.
  const autosave = useAutosave(surface === 'guided' ? source : initialSource, onSave);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SaveIndicator state={autosave.state} savedAt={autosave.savedAt} onRetry={autosave.retry} />
        <SurfaceSwitch value={surface} onChange={setSurface} />
      </div>

      {surface === 'guided' ? (
        <>
          {validationErrors.length > 0 && (
            <div
              role="alert"
              className="border border-red-700/30 bg-red-50/60 p-4 text-sm text-red-900"
            >
              <div className="kicker mb-2 text-red-900/80">Validation errors</div>
              <ul className="space-y-1">
                {validationErrors.map((err, i) => (
                  <li key={i} className="flex gap-2">
                    <code className="font-mono text-red-900/80">{err.path || '<root>'}</code>
                    <span>· {err.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <GuidedEditor
            source={source}
            sections={sections}
            onChange={setSource}
            vocabs={vocabs}
            startHereId={startHereId}
          />
        </>
      ) : (
        <MarkdownEditor
          initialMarkdown={initialSource}
          onSave={async (md) => {
            setSource(md);
            return onSave(md);
          }}
          saving={saving}
          validationErrors={validationErrors}
          saveLabel={saveLabel}
        />
      )}
    </div>
  );
}
