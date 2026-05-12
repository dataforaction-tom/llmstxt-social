/**
 * Open Org profile editor page.
 *
 * Route: /openorg/edit/:orgId/profile
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgPublishError,
  OpenOrgValidationError,
  usePublishProfile,
  useProfileMarkdown,
  useSaveProfile,
  useUnpublishProfile,
  type ValidationFieldError,
} from '../../api/openorg';
import MarkdownEditor from '../../components/openorg/MarkdownEditor';
import { PublishBadge, PublishControls } from '../../components/openorg/PublishToggle';

export default function EditProfilePage() {
  const { orgId: rawOrgId } = useParams<{ orgId: string }>();
  // Resolve to a stable string so hook inputs don't flip between undefined and
  // a value across renders; hooks are then unconditionally called below.
  const orgId = rawOrgId ?? '';

  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [publishError, setPublishError] = useState<string | null>(null);

  const profile = useProfileMarkdown(orgId);
  const save = useSaveProfile(orgId);
  const publish = usePublishProfile(orgId);
  const unpublish = useUnpublishProfile(orgId);

  if (!orgId) {
    return <div className="p-6 text-red-700">Missing org_id in URL.</div>;
  }

  if (profile.isLoading) {
    return <div className="p-6 text-gray-500">Loading profile…</div>;
  }
  if (profile.isError) {
    return (
      <div className="p-6 text-red-700">
        Failed to load profile: {String(profile.error)}
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

  const published = Boolean(profile.data?.published);
  const mutating = publish.isPending || unpublish.isPending;

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">Editing · Profile</div>
          <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="display-head text-3xl font-medium leading-tight sm:text-4xl">
                Edit organisation profile
              </h1>
              <p className="mt-2 flex items-center gap-3 text-sm text-muted">
                <code className="font-mono text-ink">{orgId}</code>
                <PublishBadge published={published} />
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
          initialMarkdown={profile.data?.markdown ?? ''}
          onSave={handleSave}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save profile"
        />
      </div>
    </div>
  );
}

