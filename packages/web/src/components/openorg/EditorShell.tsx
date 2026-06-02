import { useEffect, useState } from 'react';
import MarkdownEditor from './MarkdownEditor';
import GuidedEditor from './guided/GuidedEditor';
import SurfaceSwitch, { useEditorSurface, type RecordKind } from './SurfaceSwitch';
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end">
        <SurfaceSwitch value={surface} onChange={setSurface} />
      </div>

      {surface === 'guided' ? (
        <GuidedEditor
          source={source}
          sections={sections}
          onChange={setSource}
          vocabs={vocabs}
          startHereId={startHereId}
        />
      ) : (
        <MarkdownEditor
          initialMarkdown={source}
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
