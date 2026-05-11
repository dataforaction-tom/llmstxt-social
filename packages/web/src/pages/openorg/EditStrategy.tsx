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
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold text-gray-900">Edit strategy</h1>
        <p className="mt-1 text-sm text-gray-500">
          <code className="font-mono">{orgId}</code> · {slug}
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
  );
}
