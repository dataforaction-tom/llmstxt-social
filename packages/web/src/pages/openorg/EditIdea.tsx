/**
 * Open Org idea editor page.
 *
 * Route: /openorg/edit/:orgId/ideas/:slug
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgPublishError,
  OpenOrgValidationError,
  useIdeaMarkdown,
  usePublishIdea,
  useSaveIdea,
  useUnpublishIdea,
  type ValidationFieldError,
} from '../../api/openorg';
import MarkdownEditor from '../../components/openorg/MarkdownEditor';
import { PublishBadge, PublishControls } from '../../components/openorg/PublishToggle';

export default function EditIdeaPage() {
  const { orgId: rawOrgId, slug: rawSlug } = useParams<{ orgId: string; slug: string }>();
  const orgId = rawOrgId ?? '';
  const slug = rawSlug ?? '';

  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [publishError, setPublishError] = useState<string | null>(null);

  const idea = useIdeaMarkdown(orgId, slug);
  const save = useSaveIdea(orgId, slug);
  const publish = usePublishIdea(orgId, slug);
  const unpublish = useUnpublishIdea(orgId, slug);

  if (!orgId || !slug) {
    return <div className="p-6 text-red-700">Missing org_id or slug in URL.</div>;
  }

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

  const handlePublish = async () => {
    setPublishError(null);
    try {
      await publish.mutateAsync();
    } catch (err) {
      if (err instanceof OpenOrgPublishError) {
        setPublishError(err.detail);
      } else {
        throw err;
      }
    }
  };

  const handleUnpublish = async () => {
    setPublishError(null);
    try {
      await unpublish.mutateAsync();
    } catch (err) {
      if (err instanceof OpenOrgPublishError) {
        setPublishError(err.detail);
      } else {
        throw err;
      }
    }
  };

  const published = Boolean(idea.data?.published);
  const mutating = publish.isPending || unpublish.isPending;

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">Editing · Idea</div>
          <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="display-head text-3xl font-medium leading-tight sm:text-4xl">
                Edit idea
              </h1>
              <p className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
                <code className="font-mono text-ink">{orgId}</code>
                <span className="text-rule">·</span>
                <span className="font-mono">{slug}</span>
                <PublishBadge published={published} noun="Idea" />
              </p>
            </div>
            <PublishControls
              published={published}
              busy={mutating}
              onPublish={handlePublish}
              onUnpublish={handleUnpublish}
            />
          </div>
          {publishError && (
            <div
              role="alert"
              className="mt-4 border border-red-700/30 bg-red-50/60 p-3 text-sm text-red-900"
            >
              {publishError}
            </div>
          )}
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
