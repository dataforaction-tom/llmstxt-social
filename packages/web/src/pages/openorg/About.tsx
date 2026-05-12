/**
 * Public "About Open Org" page.
 *
 * Route: /openorg/about (per spec section 4).
 * Explains what Open Org is, why it exists, and how to participate.
 * Linked from the Discover header. Stays static — no API calls.
 */

import { Link } from 'react-router-dom';

export default function AboutPage() {
  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="kicker num">About</div>
        <h1 className="display-head mt-2 text-4xl font-medium leading-tight">
          Open Org
        </h1>
        <p className="mt-4 max-w-prose text-lg text-ink/90">
          Open Org is a way for charities and social-sector organisations to
          publish a machine-readable profile of who they are, what they do,
          and what they're trying to achieve. Profiles federate via the
          <a
            href="https://murmurations.network"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 underline hover:text-ink"
          >
            Murmurations
          </a>{' '}
          index, so any tool that speaks the schema can discover them.
        </p>

        <Section title="The data model">
          <p className="text-base leading-relaxed">
            Each organisation has a <strong>profile</strong> (who you are),
            and may publish <strong>strategies</strong> (what you're trying
            to do over the next few years) and <strong>ideas</strong>{' '}
            (specific proposals you'd like to advance). All three are
            written as markdown with YAML frontmatter — the bridge between
            human writing and machine validation.
          </p>
        </Section>

        <Section title="What this build covers (Phase 1)">
          <ul className="ml-5 list-disc space-y-2 text-base">
            <li>
              <strong>Profile generator</strong> — charity number in, Open Org
              JSON out. Uses the Charity Commission API and your website to
              fill as much as possible automatically.
            </li>
            <li>
              <strong>Strategy &amp; idea creator</strong> — a guided chat
              that turns a 15-minute conversation into a structured strategy
              or idea document, ready to edit.
            </li>
            <li>
              <strong>Markdown editor</strong> — your profile lives at a URL
              you can keep editing forever. Every save snapshots the previous
              version so nothing is lost.
            </li>
            <li>
              <strong>Murmurations connector</strong> — publishing pushes a
              tiny envelope into the federated index. Discovery clients
              elsewhere can find you without us holding the directory.
            </li>
            <li>
              <strong>Discovery page</strong> — find organisations and ideas
              across the network by theme, area, and status.
            </li>
          </ul>
        </Section>

        <Section title="What's not here yet">
          <ul className="ml-5 list-disc space-y-2 text-base">
            <li>
              Funder-side tooling, access control, and grant flows — Phase 2.
            </li>
            <li>Strategy matching and cluster detection — Phase 3.</li>
            <li>
              Linkage to outcome-tracking systems such as
              <a
                href="https://docs.hypercerts.org"
                target="_blank"
                rel="noopener noreferrer"
                className="ml-1 underline hover:text-ink"
              >
                Hypercerts
              </a>{' '}
              for evidence — Phase 4.
            </li>
          </ul>
        </Section>

        <Section title="Get started">
          <p className="text-base leading-relaxed">
            If you run a UK charity, you already have an Open Org profile in
            waiting — generated from your Charity Commission record. Claim it
            and start editing:
          </p>
          <p className="mt-3">
            <Link
              to="/openorg/generate"
              className="bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-primary-700"
            >
              Generate your profile →
            </Link>
          </p>
        </Section>

        <Section title="Browse the network">
          <ul className="ml-5 list-disc space-y-1 text-base">
            <li>
              <Link to="/openorg/discover" className="underline hover:text-ink">
                Organisations
              </Link>
            </li>
            <li>
              <Link to="/openorg/ideas" className="underline hover:text-ink">
                Ideas
              </Link>
            </li>
          </ul>
        </Section>

        <p className="mt-12 text-xs text-muted">
          Built by Good Ship. Source at{' '}
          <a
            href="https://github.com/dataforaction-tom/llmstxt-social"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-ink"
          >
            github.com/dataforaction-tom/llmstxt-social
          </a>
          .
        </p>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10 border-t border-rule pt-6">
      <h2 className="display-head mb-3 text-2xl font-medium">{title}</h2>
      {children}
    </section>
  );
}
