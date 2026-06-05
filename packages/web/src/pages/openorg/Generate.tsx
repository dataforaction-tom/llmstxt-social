/**
 * Public "Generate your Open Org profile" page.
 *
 * Spec section 1 + section 2's end-to-end flow: anyone with a UK charity
 * number can kick off generation. We don't authenticate the requester —
 * they prove ownership later by clicking the claim link emailed to the
 * address they entered.
 *
 * Route: /openorg/generate (public)
 */

import { useEffect, useRef, useState } from 'react';

import {
  generateProfile,
  lookupCharity,
  useGenerateStatus,
  OpenOrgGenerateError,
} from '../../api/openorg';
import GenerateLiveStatus from '../../components/openorg/GenerateLiveStatus';

const CHARITY_NUMBER_RE = /^[0-9]{6,8}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface Submitted {
  charityNumber: string;
  email: string;
  orgId: string;
}

export default function GeneratePage() {
  const [charityNumber, setCharityNumber] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<Submitted | null>(null);
  const [lookupName, setLookupName] = useState<string | null>(null);
  const lookupTimer = useRef<number | null>(null);

  useEffect(() => {
    const value = charityNumber.trim();
    if (lookupTimer.current !== null) {
      window.clearTimeout(lookupTimer.current);
      lookupTimer.current = null;
    }
    if (!CHARITY_NUMBER_RE.test(value)) {
      setLookupName(null);
      return undefined;
    }
    lookupTimer.current = window.setTimeout(() => {
      lookupCharity(value)
        .then((r) => setLookupName(r.name))
        .catch(() => setLookupName(null));
    }, 400);
    return () => {
      if (lookupTimer.current !== null) {
        window.clearTimeout(lookupTimer.current);
        lookupTimer.current = null;
      }
    };
  }, [charityNumber]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const number = charityNumber.trim();
    const owner = email.trim();
    if (!CHARITY_NUMBER_RE.test(number)) {
      setError('Charity number must be 6 to 8 digits.');
      return;
    }
    if (!EMAIL_RE.test(owner)) {
      setError('Please enter a valid email address.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await generateProfile(number, owner);
      setSubmitted({ charityNumber: number, email: owner, orgId: response.org_id });
    } catch (err) {
      if (err instanceof OpenOrgGenerateError) {
        setError(err.detail);
      } else {
        setError('Something went wrong. Please try again in a moment.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const statusQuery = useGenerateStatus(submitted?.orgId ?? '', Boolean(submitted));

  if (submitted) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <div className="kicker num">Generation kicked off</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Drafting your profile
          </h1>
          <p className="mt-4 max-w-prose text-sm text-muted">
            We're emailing <strong>{submitted.email}</strong> a one-time link
            you can use to claim and edit the draft.
          </p>
          <div className="mt-6">
            {statusQuery.data && (
              <GenerateLiveStatus status={statusQuery.data} onTimeout={() => undefined} />
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-2xl px-6 py-16">
        <div className="kicker num">Generate</div>
        <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
          Open Org profile in one minute
        </h1>
        <p className="mt-4 max-w-prose text-lg text-ink/90">
          Enter your UK charity number. We'll pull what's already public —
          Charity Commission filings, your website — and draft a profile you
          can review, edit, and publish to the federated network.
        </p>
        <p className="mt-3 max-w-prose text-sm text-muted">
          No account. We'll email you a one-time claim link when the draft is
          ready, and that link signs you in.
        </p>

        {/* noValidate: we do all validation in JS and surface a single, styled
            error region. HTML5 validation would short-circuit the submit on
            "not an email" before our handler runs. */}
        <form onSubmit={handleSubmit} noValidate className="mt-8 grid gap-5">
          <label className="flex flex-col text-sm">
            <span className="kicker mb-2">Charity number</span>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={charityNumber}
              onChange={(e) => setCharityNumber(e.target.value)}
              placeholder="1234567"
              className="border border-rule bg-paper px-3 py-2 text-base"
              required
              disabled={submitting}
            />
            <span className="mt-1 text-xs text-muted">
              6 to 8 digits. England &amp; Wales registrations only for now.
            </span>
            {lookupName && (
              <span className="mt-1 text-xs text-emerald-700">Match: {lookupName}</span>
            )}
          </label>

          <label className="flex flex-col text-sm">
            <span className="kicker mb-2">Your email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@your-charity.org"
              className="border border-rule bg-paper px-3 py-2 text-base"
              required
              disabled={submitting}
            />
            <span className="mt-1 text-xs text-muted">
              Where we'll send the one-time claim link. Use an address you
              control as an admin or trustee.
            </span>
          </label>

          {error && (
            <div
              role="alert"
              className="border border-red-700/30 bg-red-50/60 p-3 text-sm text-red-900"
            >
              {error}
            </div>
          )}

          <p className="text-xs italic text-muted">
            We won't publish anything without your say-so.
          </p>

          <div>
            <button
              type="submit"
              disabled={submitting}
              className="bg-ink px-5 py-2 text-sm font-medium text-paper hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? 'Generating…' : 'Generate profile'}
            </button>
          </div>
        </form>

        <p className="mt-12 text-xs text-muted">
          By submitting you agree the email address is one you control. We
          use it only for the claim link and to notify you of significant
          changes to the profile.
        </p>
      </div>
    </div>
  );
}
