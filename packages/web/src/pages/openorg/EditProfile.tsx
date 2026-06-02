/**
 * Open Org profile editor page.
 *
 * Route: /openorg/edit/:orgId/profile
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { Link, useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgPublishError,
  OpenOrgValidationError,
  useHistory,
  usePublishProfile,
  useProfileMarkdown,
  useRestoreVersion,
  useSaveProfile,
  useUnpublishProfile,
  type HistoryEntry,
  type ValidationFieldError,
} from '../../api/openorg';
import EditorShell from '../../components/openorg/EditorShell';
import PublishStrip from '../../components/openorg/PublishStrip';
import { PROFILE_SECTIONS } from '../../components/openorg/guided/sections/profile';
import { useThemes } from '../../api/openorg';

export default function EditProfilePage() {
  const { orgId: rawOrgId } = useParams<{ orgId: string }>();
  // Resolve to a stable string so hook inputs don't flip between undefined and
  // a value across renders; hooks are then unconditionally called below.
  const orgId = rawOrgId ?? '';

  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [justPublishedAt, setJustPublishedAt] = useState<Date | undefined>();

  const profile = useProfileMarkdown(orgId);
  const themes = useThemes();
  const save = useSaveProfile(orgId);
  const publish = usePublishProfile(orgId);
  const unpublish = useUnpublishProfile(orgId);
  const history = useHistory(orgId);
  const restore = useRestoreVersion(orgId);

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
      setJustPublishedAt(new Date());
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
  const liveUrl = `https://openorg.good-ship.co.uk/openorg/${orgId}`;

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
              </p>
            </div>
            <PublishStrip
              published={published}
              busy={mutating}
              onPublish={handlePublish}
              onUnpublish={handleUnpublish}
              liveUrl={liveUrl}
              justPublishedAt={justPublishedAt}
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

        <EditorShell
          kind="profile"
          initialSource={profile.data?.markdown ?? ''}
          sections={PROFILE_SECTIONS}
          onSave={handleSave}
          vocabs={{
            themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })),
          }}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save profile"
        />

        <HistoryPanel
          versions={history.data ?? []}
          onRestore={async (id) => {
            await restore.mutateAsync(id);
          }}
          busy={restore.isPending}
        />

        {/* Spec section 2 mode 3: blank-template creation entry points. */}
        <section className="mt-12 border-t border-rule pt-6">
          <div className="kicker num mb-3">Add a strategy or idea</div>
          <p className="mb-4 max-w-prose text-sm text-muted">
            Use the guided chat creator for a conversational walkthrough, or
            start with a blank template if you'd rather write it yourself.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to={`/openorg/${orgId}/create/strategy`}
              className="border border-rule px-4 py-2 text-sm text-ink hover:bg-paper-2"
            >
              Chat: new strategy
            </Link>
            <Link
              to={`/openorg/edit/${orgId}/strategies/new`}
              className="border border-rule px-4 py-2 text-sm text-ink hover:bg-paper-2"
            >
              Blank template: new strategy
            </Link>
            <Link
              to={`/openorg/${orgId}/create/idea`}
              className="border border-rule px-4 py-2 text-sm text-ink hover:bg-paper-2"
            >
              Chat: new idea
            </Link>
            <Link
              to={`/openorg/edit/${orgId}/ideas/new`}
              className="border border-rule px-4 py-2 text-sm text-ink hover:bg-paper-2"
            >
              Blank template: new idea
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}

function HistoryPanel({
  versions,
  onRestore,
  busy,
}: {
  versions: HistoryEntry[];
  onRestore: (id: string) => Promise<void>;
  busy: boolean;
}) {
  if (versions.length <= 1) {
    // First save shows up in history; show the panel only once there's
    // something to compare against.
    return null;
  }
  return (
    <section className="mt-12 border-t border-rule pt-6">
      <details>
        <summary className="kicker num cursor-pointer select-none">
          History · {versions.length} versions
        </summary>
        <ul className="mt-4 divide-y divide-rule border border-rule">
          {versions.map((v, i) => {
            const isLatest = i === 0;
            return (
              <li
                key={v.id}
                className="flex flex-wrap items-center justify-between gap-3 px-3 py-2 text-sm"
              >
                <div>
                  <span className="font-mono text-xs text-muted">
                    {formatVersionTime(v.created_at)}
                  </span>
                  {isLatest && (
                    <span className="ml-2 text-xs uppercase tracking-wider text-emerald-700">
                      current
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  disabled={busy || isLatest}
                  onClick={() => onRestore(v.id)}
                  className="border border-rule px-3 py-1 text-xs hover:bg-paper-2 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy ? 'Restoring…' : 'Restore'}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs text-muted">
          Restoring is non-destructive — it creates a new version pointing to
          the chosen snapshot. Nothing is overwritten.
        </p>
      </details>
    </section>
  );
}

function formatVersionTime(iso: string): string {
  if (!iso) return '(unknown)';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

