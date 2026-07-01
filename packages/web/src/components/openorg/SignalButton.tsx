/**
 * SignalButton — lets a funder express interest in a published idea.
 *
 * Phase 1: no auth, all fields optional (anonymous signalling is fine).
 * Shows a success confirmation after submit, or an inline error on failure.
 */

import { useState } from 'react';
import { signalIdea, type SignalBody, type SignalOut } from '../../api/openorg';

export default function SignalButton({ orgId, slug }: { orgId: string; slug: string }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<SignalOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');

  if (done) {
    return (
      <div className="mt-2 border-l-2 border-teal pl-3 text-sm text-navy">
        <p className="font-medium">Thank you — your signal of interest was sent.</p>
        {done.funder_name && <p className="text-grey-blue">From: {done.funder_name}</p>}
        <button
          type="button"
          onClick={() => {
            setDone(null);
            setOpen(false);
            setName('');
            setEmail('');
            setMessage('');
          }}
          className="mt-1 text-xs underline text-grey-blue hover:text-navy"
        >
          Send another
        </button>
      </div>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2 border border-rule bg-cream px-3 py-1 text-xs font-medium text-navy hover:bg-cream-dark"
      >
        Express interest
      </button>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const body: SignalBody = { funder_name: name, funder_email: email, message };
      const result = await signalIdea(orgId, slug, body);
      setDone(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-2 space-y-2 border-l-2 border-rule pl-3">
      <div>
        <label className="block text-xs text-grey-blue">
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-0.5 w-full border border-rule bg-cream px-2 py-1 text-sm text-navy"
            placeholder="Optional"
          />
        </label>
      </div>
      <div>
        <label className="block text-xs text-grey-blue">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-0.5 w-full border border-rule bg-cream px-2 py-1 text-sm text-navy"
            placeholder="Optional"
          />
        </label>
      </div>
      <div>
        <label className="block text-xs text-grey-blue">
          Message
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="mt-0.5 w-full border border-rule bg-cream px-2 py-1 text-sm text-navy"
            placeholder="Optional"
            rows={2}
          />
        </label>
      </div>
      {error && <p className="text-xs text-red-700">Something went wrong — {error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="bg-teal px-3 py-1 text-xs font-medium text-cream hover:bg-teal-light disabled:opacity-50"
        >
          {submitting ? 'Sending…' : 'Send signal'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="border border-rule px-3 py-1 text-xs text-navy hover:bg-cream-dark"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}