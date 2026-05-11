/**
 * Strategy / idea chat-creator page.
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
 * Auth: gated by ProtectedRoute; the backend require_org_admin gate
 * cross-checks the user is an admin of org_id.
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

  if (!orgId || !kind || (kind !== 'strategy' && kind !== 'idea')) {
    return (
      <div className="p-6 text-red-700">
        Bad URL. Expected /openorg/&lt;org_id&gt;/create/&lt;strategy|idea&gt;.
      </div>
    );
  }
  const typedKind = kind as CreatorKind;

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

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await createCreatorSession(orgId, typedKind, upload ?? undefined);
      setSessionId(session.session_id);
      setCurrentMarkdown(session.current_markdown);
      // Hydrate any seed history (uploaded doc primes the first user turn).
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
    // Push a placeholder assistant turn we mutate as deltas arrive.
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

  if (!sessionId) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-6">
        <h1 className="text-2xl font-semibold text-gray-900">
          Create {typedKind === 'strategy' ? 'a strategy' : 'an idea'}
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          Organisation: <code className="font-mono">{orgId}</code>
        </p>
        <p className="mt-4 text-sm text-gray-700">
          We'll have a short conversation to build a draft, then drop you into the
          editor for a final pass. Optionally upload an existing document
          (PDF, Word, or text) as a starting point.
        </p>

        <label className="mt-6 block text-sm">
          <span className="block text-gray-700">Primer document (optional)</span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => setUpload(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm"
          />
        </label>

        <button
          type="button"
          onClick={start}
          disabled={starting}
          className="mt-6 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
        >
          {starting ? 'Starting…' : 'Start session'}
        </button>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Creating {typedKind === 'strategy' ? 'a strategy' : 'an idea'}
          </h1>
          <p className="text-xs text-gray-500">
            <code className="font-mono">{orgId}</code> · session {sessionId.slice(0, 8)}
          </p>
        </div>
        <button
          type="button"
          onClick={finalize}
          disabled={!currentMarkdown || finalising}
          className="rounded-md bg-primary-600 px-3 py-2 text-sm text-white hover:bg-primary-500 disabled:opacity-50"
        >
          {finalising ? 'Finalising…' : 'Finalise & open editor'}
        </button>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="flex h-[70vh] flex-col rounded-md border border-gray-200 bg-white">
          <div
            ref={transcriptRef}
            className="flex-1 overflow-y-auto px-3 py-3 text-sm"
            aria-live="polite"
          >
            {turns.length === 0 && (
              <p className="text-gray-500">
                Send your first message to start. The assistant will ask one
                question at a time.
              </p>
            )}
            {turns.map((turn, i) => (
              <div
                key={i}
                className={
                  'mb-2 rounded px-2 py-1 ' +
                  (turn.role === 'user'
                    ? 'bg-primary-50 text-primary-900'
                    : 'bg-gray-50 text-gray-900')
                }
              >
                <div className="text-[10px] uppercase tracking-wide text-gray-500">
                  {turn.role}
                </div>
                <div className="whitespace-pre-wrap">{turn.content}</div>
              </div>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!pending) void send();
            }}
            className="flex gap-2 border-t border-gray-200 px-3 py-2"
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={2}
              placeholder="Type your message…"
              className="flex-1 resize-none rounded border border-gray-300 px-2 py-1 text-sm"
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
              className="self-end rounded-md bg-primary-600 px-3 py-1.5 text-sm text-white hover:bg-primary-500 disabled:opacity-50"
            >
              {pending ? '…' : 'Send'}
            </button>
          </form>
        </section>

        <section className="h-[70vh] overflow-y-auto rounded-md border border-gray-200 bg-gray-50 px-4 py-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Live draft
          </h2>
          {currentMarkdown ? (
            <article className="prose prose-sm max-w-none text-gray-900">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentMarkdown}</ReactMarkdown>
            </article>
          ) : (
            <p className="text-sm text-gray-500">
              The draft updates after each exchange.
            </p>
          )}
        </section>
      </div>

      {error ? (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}
    </div>
  );
}
