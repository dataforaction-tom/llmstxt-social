/**
 * Markdown editor with side-by-side preview — civic editorial styling.
 *
 * Left: CodeMirror 6 with markdown + YAML highlighting.
 *
 * Right: react-markdown preview rendered with the project's editorial
 * typography. The .editorial-preview rules live in ``index.css`` (single
 * source of truth — Create.tsx's live-draft pane uses the same class so
 * the two surfaces render identically). Frontmatter lives behind a
 * <details> disclosure so the preview reads as the document body.
 *
 * Save flow is unchanged from v1 — onSave gets the full markdown source;
 * the parent owns the API loop.
 */

import { useEffect, useMemo, useState } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { markdown, markdownLanguage } from '@codemirror/lang-markdown';
import { yaml } from '@codemirror/lang-yaml';
import type { LanguageDescription } from '@codemirror/language';
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

function splitFrontmatter(source: string): { frontmatter: string; body: string } {
  if (!source.startsWith('---\n') && !source.startsWith('---\r\n')) {
    return { frontmatter: '', body: source };
  }
  const closing = source.indexOf('\n---', 4);
  if (closing === -1) return { frontmatter: source, body: '' };
  const frontmatter = source.slice(0, closing + 4);
  const rest = source.slice(closing + 4);
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
      markdown({
        base: markdownLanguage,
        codeLanguages: [
          {
            name: 'yaml',
            alias: ['yaml'],
            extensions: ['yml', 'yaml'],
            support: yaml(),
          } as unknown as LanguageDescription,
        ],
      }),
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
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <span className="kicker" aria-live="polite">
          {dirty ? '● Unsaved' : 'Saved'}
        </span>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !dirty}
          className="bg-ink px-4 py-1.5 text-sm font-medium text-paper transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? 'Saving…' : saveLabel}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-0 border border-rule bg-paper lg:grid-cols-2 lg:divide-x lg:divide-rule">
        <div className="flex flex-col">
          <div className="kicker border-b border-rule px-3 py-2">Source</div>
          <CodeMirror
            value={source}
            height="62vh"
            extensions={extensions}
            onChange={handleChange}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              highlightActiveLine: true,
              autocompletion: false,
            }}
            theme="light"
            aria-label="Markdown source"
          />
        </div>

        <div className="flex flex-col">
          <div className="kicker border-b border-rule px-3 py-2">Preview</div>
          <div className="min-h-[62vh] overflow-auto px-6 py-5">
            {frontmatter && (
              <details className="mb-4 text-xs text-muted">
                <summary className="kicker cursor-pointer select-none">
                  Frontmatter
                </summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-sm bg-paper-2 px-3 py-2 font-mono text-[11px] leading-relaxed text-ink/80">
                  {frontmatter}
                </pre>
              </details>
            )}

            <article className="editorial-preview text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
            </article>
          </div>
        </div>
      </div>

      {validationErrors.length > 0 && (
        <div className="border border-red-700/30 bg-red-50/60 p-4 text-sm text-red-900">
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
    </div>
  );
}
