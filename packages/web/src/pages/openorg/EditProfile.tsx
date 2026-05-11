/**
 * Open Org profile editor page.
 *
 * Route: /openorg/edit/:orgId/profile
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgValidationError,
  useProfileMarkdown,
  useSaveProfile,
  type ValidationFieldError,
} from '../../api/openorg';
import MarkdownEditor from '../../components/openorg/MarkdownEditor';

export default function EditProfilePage() {
  const { orgId } = useParams<{ orgId: string }>();
  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);

  if (!orgId) {
    return <div className="p-6 text-red-700">Missing org_id in URL.</div>;
  }

  const profile = useProfileMarkdown(orgId);
  const save = useSaveProfile(orgId);

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

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">Editing · Profile</div>
          <h1 className="display-head mt-2 text-3xl font-medium leading-tight sm:text-4xl">
            Edit organisation profile
          </h1>
          <p className="mt-2 text-sm text-muted">
            <code className="font-mono text-ink">{orgId}</code>
          </p>
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
