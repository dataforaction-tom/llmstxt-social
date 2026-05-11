/**
 * Open Org idea editor page.
 *
 * Route: /openorg/edit/:orgId/ideas/:slug
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgValidationError,
  useIdeaMarkdown,
  useSaveIdea,
  type ValidationFieldError,
} from '../../api/openorg';
import MarkdownEditor from '../../components/openorg/MarkdownEditor';

export default function EditIdeaPage() {
  const { orgId, slug } = useParams<{ orgId: string; slug: string }>();
  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);

  if (!orgId || !slug) {
    return <div className="p-6 text-red-700">Missing org_id or slug in URL.</div>;
  }

  const idea = useIdeaMarkdown(orgId, slug);
  const save = useSaveIdea(orgId, slug);

  if (idea.isLoading) {
    return <div className="p-6 text-gray-500">Loading idea…</div>;
  }
  if (idea.isError) {
    return (
      <div className="p-6 text-red-700">
        Failed to load idea: {String(idea.error)}
      </div>
    );
  }

  const handleSave = async (markdown: string) => {
    setValidationErrors([]);
    try {
      await save.mutateAsync(markdown);
    } catch (err) {
      if (err instanceof OpenOrgValidationError) {
        setValidationErrors(err.errors);
      } else {
        throw err;
      }
    }
  };

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">Editing · Idea</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Edit idea
          </h1>
          <p className="mt-2 text-sm text-muted">
            <code className="font-mono text-ink">{orgId}</code>
            <span className="mx-2 text-rule">·</span>
            <span className="font-mono">{slug}</span>
          </p>
        </header>

        <MarkdownEditor
          initialMarkdown={idea.data?.markdown ?? ''}
          onSave={handleSave}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save idea"
        />
      </div>
    </div>
  );
}
