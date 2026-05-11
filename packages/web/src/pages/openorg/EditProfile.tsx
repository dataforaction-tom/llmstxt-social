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
    <div className="mx-auto max-w-4xl px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold text-gray-900">Edit profile</h1>
        <p className="mt-1 text-sm text-gray-500">
          Organisation: <code className="font-mono">{orgId}</code>
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
  );
}
