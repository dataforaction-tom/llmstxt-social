/**
 * Strategy / idea chat-creator page — civic editorial styling.
 *
 * Route: /openorg/:orgId/create/:kind  (kind in {strategy, idea})
 *
 * Flow:
 *   1. Choose to upload a primer doc (optional) or start fresh.
 *   2. Chat — each user message streams an assistant reply via SSE; the
 *      assistant's update_current_markdown tool call drives the live
 *      preview pane on the right.
 *   3. Finalize — POST .../finalize, navigate to the editor for the
 *      newly-created OrgStrategy or OrgIdea row.
 *
 * Layout: two-column on lg+. Left: transcript styled like a printed
 * interview (role labels in small caps, left rule per turn, no chat
 * bubbles). Right: a paper-tone live draft using the same
 * .editorial-preview rules as MarkdownEditor.tsx — defined in index.css
 * so both surfaces stay identical.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  type CreatorKind,
  type CreatorSessionDetail,
  createCreatorSession,
  fetchCreatorSession,
  finalizeCreatorSession,
  streamCreatorMessage,
} from '../../api/openorg';


type TurnRole = 'user' | 'assistant';
interface Turn {
  role: TurnRole;
  content: string;
}


export default function CreatePage() {
  const { orgId, kind } = useParams<{ orgId: string; kind: string }>();
  const navigate = useNavigate();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [currentMarkdown, setCurrentMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<File | null>(null);
  const [starting, setStarting] = useState(false);
  const [finalising, setFinalising] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [turns]);

  // Hooks must run unconditionally, so validate the URL only after they're
  // all declared.
  if (!orgId || !kind || (kind !== 'strategy' && kind !== 'idea')) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-12 text-red-800">
          Bad URL. Expected{' '}
          <code className="font-mono">
            /openorg/&lt;org_id&gt;/create/&lt;strategy|idea&gt;
          </code>
          .
        </div>
      </div>
    );
  }
  const typedKind = kind as CreatorKind;

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await createCreatorSession(orgId, typedKind, upload ?? undefined);
      setSessionId(session.session_id);
      setCurrentMarkdown(session.current_markdown);
      const detail: CreatorSessionDetail = await fetchCreatorSession(session.session_id);
      setTurns(
        detail.conversation_history.map((t) => ({ role: t.role, content: t.content })),
      );
    } catch (err) {
      setError(`Couldn't start the session: ${String(err)}`);
    } finally {
      setStarting(false);
    }
  };

  const send = async () => {
    if (!sessionId || !draft.trim()) return;
    const message = draft.trim();
    setDraft('');
    setPending(true);
    setError(null);
    setTurns((prev) => [...prev, { role: 'user', content: message }]);
    setTurns((prev) => [...prev, { role: 'assistant', content: '' }]);

    try {
      await streamCreatorMessage(
        sessionId,
        message,
        (deltaText) => {
          setTurns((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { role: 'assistant', content: last.content + deltaText };
            }
            return next;
          });
        },
        (payload) => {
          if (payload.current_markdown !== undefined) {
            setCurrentMarkdown(payload.current_markdown);
          }
        },
      );
    } catch (err) {
      setError(`Stream failed: ${String(err)}`);
    } finally {
      setPending(false);
    }
  };

  const finalize = async () => {
    if (!sessionId) return;
    setFinalising(true);
    setError(null);
    try {
      const result = await finalizeCreatorSession(sessionId);
      const editPath =
        result.kind === 'strategy'
          ? `/openorg/edit/${result.org_id}/strategies/${result.slug}`
          : `/openorg/edit/${result.org_id}/ideas/${result.slug}`;
      navigate(editPath);
    } catch (err) {
      setError(`Couldn't finalise: ${String(err)}`);
    } finally {
      setFinalising(false);
    }
  };

  // ---------- Pre-session intro ------------------------------------------
  if (!sessionId) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <div className="kicker num">Creating · {typedKind}</div>
          <h1 className="display-head mt-2 text-4xl font-medium leading-tight">
            A short conversation,
            <br />
            then a draft you can edit.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/90">
            We'll ask one question at a time and build the document as we go.
            When you're done, you'll land in the editor for a final pass.
          </p>
          <p className="mt-2 text-sm text-muted">
            Organisation:{' '}
            <code className="font-mono text-ink">{orgId}</code>
          </p>

          <div className="rule-h mt-10 border-t border-rule pt-8">
            <span className="kicker">Optional · primer document</span>
            <p className="mt-2 text-sm text-muted">
              Got an existing strategy doc? Drop it in and we'll start from
              there. PDF, Word, or plain text.
            </p>
            <label className="mt-3 flex cursor-pointer items-center gap-3 border border-dashed border-rule bg-paper-2/40 px-4 py-3 text-sm text-ink hover:bg-paper-2">
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => setUpload(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
              <span className="font-mono text-xs text-muted">
                {upload ? '✓' : '+'}
              </span>
              <span>{upload ? upload.name : 'Choose a file'}</span>
            </label>
          </div>

          <button
            type="button"
            onClick={start}
            disabled={starting}
            className="mt-10 bg-ink px-5 py-2.5 text-sm font-medium text-paper transition hover:bg-primary-700 disabled:opacity-50"
          >
            {starting ? 'Starting…' : 'Begin session →'}
          </button>
          {error ? <p className="mt-4 text-sm text-red-800">{error}</p> : null}
        </div>
      </div>
    );
  }

  // ---------- Active session ---------------------------------------------
  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex items-end justify-between gap-6">
          <div>
            <div className="kicker num">In session · {typedKind}</div>
            <h1 className="display-head mt-1 text-2xl font-medium leading-tight">
              Building your {typedKind === 'strategy' ? 'strategy' : 'idea'}
            </h1>
            <p className="mt-1 text-xs text-muted">
              <code className="font-mono">{orgId}</code>
              <span className="mx-2 text-rule">·</span>
              session <code className="font-mono">{sessionId.slice(0, 8)}</code>
            </p>
          </div>
          <button
            type="button"
            onClick={finalize}
            disabled={!currentMarkdown || finalising}
            className="bg-ink px-4 py-2 text-sm text-paper transition hover:bg-primary-700 disabled:opacity-40"
          >
            {finalising ? 'Finalising…' : 'Finalise & open editor'}
          </button>
        </header>

        <div className="grid grid-cols-1 gap-0 border border-rule lg:grid-cols-2 lg:divide-x lg:divide-rule">
          {/* --- transcript ---------------------------------------- */}
          <section className="flex h-[72vh] flex-col bg-paper">
            <div className="kicker border-b border-rule px-3 py-2">Conversation</div>
            <div
              ref={transcriptRef}
              className="flex-1 overflow-y-auto px-5 py-5"
              aria-live="polite"
            >
              {turns.length === 0 && (
                <p className="text-sm italic text-muted">
                  Send your first message to begin. The assistant will ask one
                  question at a time.
                </p>
              )}
              <ol className="space-y-5">
                {turns.map((turn, i) => (
                  <li
                    key={i}
                    className={
                      'border-l-2 pl-4 ' +
                      (turn.role === 'user'
                        ? 'border-ink/80'
                        : 'border-primary-600/70')
                    }
                  >
                    <div
                      className={
                        'kicker mb-1 ' +
                        (turn.role === 'assistant' ? 'text-primary-700' : '')
                      }
                    >
                      {turn.role === 'user' ? 'You' : 'Assistant'}
                    </div>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
                      {turn.content || (
                        <span className="text-muted italic">thinking…</span>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!pending) void send();
              }}
              className="flex gap-2 border-t border-rule bg-paper-2/50 px-3 py-3"
            >
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                placeholder="Type your message…  (⌘/Ctrl + Enter to send)"
                className="flex-1 resize-none border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-ink focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    if (!pending) void send();
                  }
                }}
              />
              <button
                type="submit"
                disabled={!draft.trim() || pending}
                className="self-end bg-ink px-4 py-1.5 text-sm text-paper transition hover:bg-primary-700 disabled:opacity-40"
              >
                {pending ? '…' : 'Send'}
              </button>
            </form>
          </section>

          {/* --- live draft ---------------------------------------- */}
          <section className="flex h-[72vh] flex-col bg-paper-2/30">
            <div className="kicker border-b border-rule px-3 py-2">
              Live draft
            </div>
            <div className="flex-1 overflow-y-auto px-7 py-6">
              {currentMarkdown ? (
                <article className="editorial-preview text-ink">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {currentMarkdown}
                  </ReactMarkdown>
                </article>
              ) : (
                <p className="text-sm italic text-muted">
                  The draft will appear here as the conversation builds it up.
                </p>
              )}
            </div>
          </section>
        </div>

        {error ? (
          <div className="mt-4 border border-red-700/30 bg-red-50/60 p-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}
