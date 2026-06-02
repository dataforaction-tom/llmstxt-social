/**
 * "New strategy" / "New idea" — blank-template editor.
 *
 * Spec section 2: blank templates with HTML-comment guidance, for orgs that
 * prefer to write directly rather than go through the chat creator.
 *
 * Routes:
 *   /openorg/edit/:orgId/strategies/new
 *   /openorg/edit/:orgId/ideas/new
 *
 * On save: extract the ``id`` from frontmatter, PUT to the appropriate
 * .md endpoint (which creates the row if it doesn't exist), then navigate
 * the user to the editor at the canonical slug URL.
 */

import { useNavigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgValidationError,
  saveIdeaMarkdown,
  saveStrategyMarkdown,
  useThemes,
  type ValidationFieldError,
} from '../../api/openorg';
import EditorShell from '../../components/openorg/EditorShell';
import { STRATEGY_SECTIONS } from '../../components/openorg/guided/sections/strategy';
import { IDEA_SECTIONS } from '../../components/openorg/guided/sections/idea';
import { STATIC_VOCABS } from '../../components/openorg/guided/vocabs';
import { templateFor, type TemplateKind } from '../../openorgTemplates';

interface NewRecordPageProps {
  kind: TemplateKind;
}

const SLUG_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

function extractSlug(markdown: string): string | null {
  // Pull the YAML `id:` field out of the frontmatter without taking a full
  // parser dependency on the client. Frontmatter spans lines 2..(closing ---).
  // Handles three flavours: ``id: "value"``, ``id: 'value'``, ``id: value``,
  // and tolerates a trailing ``# comment`` on the same line.
  const frontmatterEnd = markdown.indexOf('\n---', 4);
  if (frontmatterEnd === -1) return null;
  const frontmatter = markdown.slice(0, frontmatterEnd);
  const match = frontmatter.match(/^id:\s*(?:"([^"]*)"|'([^']*)'|(\S+))/m);
  if (!match) return null;
  const candidate = (match[1] ?? match[2] ?? match[3] ?? '').trim();
  return SLUG_RE.test(candidate) ? candidate : null;
}

export default function NewRecordPage({ kind }: NewRecordPageProps) {
  const navigate = useNavigate();
  const { orgId: rawOrgId } = useParams<{ orgId: string }>();
  const orgId = rawOrgId ?? '';

  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [slugError, setSlugError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const themes = useThemes();

  if (!orgId) {
    return <div className="p-6 text-red-700">Missing org_id in URL.</div>;
  }

  const template = templateFor(kind);
  const noun = kind === 'strategy' ? 'strategy' : 'idea';
  const Noun = noun.charAt(0).toUpperCase() + noun.slice(1);
  const sections = kind === 'strategy' ? STRATEGY_SECTIONS : IDEA_SECTIONS;

  const handleSave = async (markdown: string) => {
    setValidationErrors([]);
    setSlugError(null);

    const slug = extractSlug(markdown);
    if (!slug) {
      setSlugError(
        `Please set a valid slug in the frontmatter \`id:\` field — lowercase letters, digits, and dashes only (you currently have the template placeholder).`,
      );
      return;
    }

    setSaving(true);
    try {
      if (kind === 'strategy') {
        await saveStrategyMarkdown(orgId, slug, markdown);
        navigate(`/openorg/edit/${orgId}/strategies/${slug}`, { replace: true });
      } else {
        await saveIdeaMarkdown(orgId, slug, markdown);
        navigate(`/openorg/edit/${orgId}/ideas/${slug}`, { replace: true });
      }
    } catch (err) {
      if (err instanceof OpenOrgValidationError) {
        setValidationErrors(err.errors);
      } else {
        throw err;
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">New · {Noun}</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            New {noun}
          </h1>
          <p className="mt-2 max-w-prose text-sm text-muted">
            The template below has placeholder prompts in
            <code className="font-mono"> &lt;!-- comments --&gt;</code>. Fill
            them in and click <strong>Save {noun}</strong>; the comments are
            stripped automatically. Set the <code className="font-mono">id</code>{' '}
            field in the frontmatter to your chosen URL-stable slug before
            saving.
          </p>
        </header>

        {slugError && (
          <div
            role="alert"
            className="mb-4 border border-red-700/30 bg-red-50/60 p-3 text-sm text-red-900"
          >
            {slugError}
          </div>
        )}

        <EditorShell
          kind={kind}
          initialSource={template}
          sections={sections}
          onSave={handleSave}
          vocabs={{
            ...STATIC_VOCABS,
            themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })),
          }}
          saving={saving}
          validationErrors={validationErrors}
          saveLabel={`Save ${noun}`}
        />
      </div>
    </div>
  );
}
