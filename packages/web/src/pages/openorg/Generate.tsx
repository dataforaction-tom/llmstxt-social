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

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { generateProfile, OpenOrgGenerateError } from '../../api/openorg';

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

  if (submitted) {
    return (
      <div className="surface-paper min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <div className="kicker num">Generation kicked off</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Check your inbox
          </h1>
          <p className="mt-4 max-w-prose text-lg text-ink">
            We're pulling the Charity Commission record for{' '}
            <code className="font-mono">{submitted.charityNumber}</code>, crawling
            the charity's website, and drafting a profile.
          </p>
          <p className="mt-3 max-w-prose text-base text-ink">
            When it's ready (usually 30–90 seconds) we'll email{' '}
            <strong>{submitted.email}</strong> a one-time link that lets you
            review, edit, and publish the profile.
          </p>
          <p className="mt-3 max-w-prose text-sm text-muted">
            The profile will live at{' '}
            <code className="font-mono">{`/openorg/${submitted.orgId}`}</code> once
            you've claimed it and clicked Publish.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 text-sm">
            <Link
              to="/openorg/discover"
              className="border border-rule px-4 py-2 hover:bg-paper-2"
            >
              Browse the network
            </Link>
            <Link
              to="/openorg/about"
              className="border border-rule px-4 py-2 hover:bg-paper-2"
            >
              What is Open Org?
            </Link>
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
