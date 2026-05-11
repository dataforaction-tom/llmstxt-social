/**
 * Open Org strategy editor page.
 *
 * Route: /openorg/edit/:orgId/strategies/:slug
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgValidationError,
  useStrategyMarkdown,
  useSaveStrategy,
  type ValidationFieldError,
} from '../../api/openorg';
import MarkdownEditor from '../../components/openorg/MarkdownEditor';

export default function EditStrategyPage() {
  const { orgId, slug } = useParams<{ orgId: string; slug: string }>();
  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);

  if (!orgId || !slug) {
    return <div className="p-6 text-red-700">Missing org_id or slug in URL.</div>;
  }

  const strategy = useStrategyMarkdown(orgId, slug);
  const save = useSaveStrategy(orgId, slug);

  if (strategy.isLoading) {
    return <div className="p-6 text-gray-500">Loading strategy…</div>;
  }
  if (strategy.isError) {
    return (
      <div className="p-6 text-red-700">
        Failed to load strategy: {String(strategy.error)}
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
          <div className="kicker num">Editing · Strategy</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Edit strategy
          </h1>
          <p className="mt-2 text-sm text-muted">
            <code className="font-mono text-ink">{orgId}</code>
            <span className="mx-2 text-rule">·</span>
            <span className="font-mono">{slug}</span>
          </p>
        </header>

        <MarkdownEditor
          initialMarkdown={strategy.data?.markdown ?? ''}
          onSave={handleSave}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save strategy"
        />
      </div>
    </div>
  );
}
