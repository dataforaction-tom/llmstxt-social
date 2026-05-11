/**
 * Markdown editor with side-by-side preview.
 *
 * Left: CodeMirror 6 with markdown + YAML highlighting (frontmatter blocks
 * get YAML colours while the body stays in markdown mode — close enough
 * for a single editor; full nested-language switching is overkill).
 *
 * Right: react-markdown preview of the body (everything after the closing
 * YAML frontmatter delimiter).
 *
 * Save flow is unchanged from the v1 textarea — onSave gets the full markdown
 * source; the parent keeps the loop with the API.
 */

import { useEffect, useMemo, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { markdown, markdownLanguage } from '@codemirror/lang-markdown';
import { yaml } from '@codemirror/lang-yaml';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ValidationFieldError } from '../../api/openorg';

interface MarkdownEditorProps {
  initialMarkdown: string;
  onSave: (markdown: string) => Promise<unknown>;
  saving?: boolean;
  validationErrors?: ValidationFieldError[];
  saveLabel?: string;
}

/** Split YAML frontmatter from body so the preview only renders the body. */
function splitFrontmatter(source: string): { frontmatter: string; body: string } {
  if (!source.startsWith('---\n') && !source.startsWith('---\r\n')) {
    return { frontmatter: '', body: source };
  }
  const closing = source.indexOf('\n---', 4);
  if (closing === -1) return { frontmatter: source, body: '' };
  const frontmatter = source.slice(0, closing + 4);
  const rest = source.slice(closing + 4);
  // Skip the newline immediately after the closing delimiter.
  return { frontmatter, body: rest.replace(/^\r?\n/, '') };
}

export default function MarkdownEditor({
  initialMarkdown,
  onSave,
  saving = false,
  validationErrors = [],
  saveLabel = 'Save',
}: MarkdownEditorProps) {
  const [source, setSource] = useState(initialMarkdown);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setSource(initialMarkdown);
    setDirty(false);
  }, [initialMarkdown]);

  const { frontmatter, body } = useMemo(() => splitFrontmatter(source), [source]);

  const extensions = useMemo(
    () => [
      markdown({ base: markdownLanguage, codeLanguages: [{ name: 'yaml', alias: ['yaml'], extensions: ['yml', 'yaml'], support: yaml() } as any] }),
    ],
    []
  );

  const handleChange = (value: string) => {
    setSource(value);
    setDirty(true);
  };

  const handleSave = async () => {
    await onSave(source);
    setDirty(false);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-gray-500" aria-live="polite">
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

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="overflow-hidden rounded-md border border-gray-300 bg-white">
          <CodeMirror
            value={source}
            height="60vh"
            extensions={extensions}
            onChange={handleChange}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              highlightActiveLine: true,
              autocompletion: false,
            }}
            aria-label="Markdown source"
          />
        </div>

        <div className="min-h-[60vh] overflow-auto rounded-md border border-gray-200 bg-gray-50 px-4 py-3">
          {frontmatter && (
            <details className="mb-3 text-xs text-gray-500">
              <summary className="cursor-pointer select-none">Frontmatter</summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-gray-600">
                {frontmatter}
              </pre>
            </details>
          )}
          <article className="prose prose-sm max-w-none text-gray-900">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </article>
        </div>
      </div>

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
