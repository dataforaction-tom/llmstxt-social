/**
 * Minimum-viable markdown editor: a styled textarea with line numbering hints
 * and validation status. CodeMirror 6 + react-markdown live preview are
 * deferred to a Step 4 polish pass — this gets the save/validate loop working.
 */

import { useEffect, useState } from 'react';
import type { ValidationFieldError } from '../../api/openorg';

interface MarkdownEditorProps {
  initialMarkdown: string;
  onSave: (markdown: string) => Promise<unknown>;
  saving?: boolean;
  validationErrors?: ValidationFieldError[];
  saveLabel?: string;
}

export default function MarkdownEditor({
  initialMarkdown,
  onSave,
  saving = false,
  validationErrors = [],
  saveLabel = 'Save',
}: MarkdownEditorProps) {
  const [markdown, setMarkdown] = useState(initialMarkdown);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setMarkdown(initialMarkdown);
    setDirty(false);
  }, [initialMarkdown]);

  const handleChange = (value: string) => {
    setMarkdown(value);
    setDirty(true);
  };

  const handleSave = async () => {
    await onSave(markdown);
    setDirty(false);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-gray-500">
          {dirty ? 'Unsaved changes' : 'All changes saved'}
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !dirty}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? 'Saving…' : saveLabel}
        </button>
      </div>

      <textarea
        value={markdown}
        onChange={(e) => handleChange(e.target.value)}
        spellCheck={false}
        className="min-h-[60vh] w-full rounded-md border border-gray-300 bg-white px-3 py-2 font-mono text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
      />

      {validationErrors.length > 0 && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <div className="font-medium">Validation errors:</div>
          <ul className="mt-1 ml-4 list-disc space-y-0.5">
            {validationErrors.map((err, i) => (
              <li key={i}>
                <code className="font-mono">{err.path || '<root>'}</code>: {err.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
