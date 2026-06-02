/**
 * Open Org strategy editor page.
 *
 * Route: /openorg/edit/:orgId/strategies/:slug
 * Auth: relies on AuthContext + backend require_org_admin.
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import {
  OpenOrgPublishError,
  OpenOrgValidationError,
  usePublishStrategy,
  useSaveStrategy,
  useStrategyMarkdown,
  useThemes,
  useUnpublishStrategy,
  type ValidationFieldError,
} from '../../api/openorg';
import EditorShell from '../../components/openorg/EditorShell';
import PublishStrip from '../../components/openorg/PublishStrip';
import { STRATEGY_SECTIONS } from '../../components/openorg/guided/sections/strategy';
import { STATIC_VOCABS } from '../../components/openorg/guided/vocabs';

export default function EditStrategyPage() {
  const { orgId: rawOrgId, slug: rawSlug } = useParams<{ orgId: string; slug: string }>();
  // Resolve to stable strings so hook inputs don't flip between undefined
  // and a value across renders; hooks are then unconditionally called below.
  const orgId = rawOrgId ?? '';
  const slug = rawSlug ?? '';

  const [validationErrors, setValidationErrors] = useState<ValidationFieldError[]>([]);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [justPublishedAt, setJustPublishedAt] = useState<Date | undefined>();

  const strategy = useStrategyMarkdown(orgId, slug);
  const save = useSaveStrategy(orgId, slug);
  const publish = usePublishStrategy(orgId, slug);
  const unpublish = useUnpublishStrategy(orgId, slug);
  const themes = useThemes();

  if (!orgId || !slug) {
    return <div className="p-6 text-red-700">Missing org_id or slug in URL.</div>;
  }

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

  const published = Boolean(strategy.data?.published);
  const mutating = publish.isPending || unpublish.isPending;
  const liveUrl = `https://openorg.good-ship.co.uk/openorg/${orgId}/strategies/${slug}`;

  return (
    <div className="surface-paper min-h-screen">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <div className="kicker num">Editing · Strategy</div>
          <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="display-head text-3xl font-medium leading-tight sm:text-4xl">
                Edit strategy
              </h1>
              <p className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
                <code className="font-mono text-ink">{orgId}</code>
                <span className="text-rule">·</span>
                <span className="font-mono">{slug}</span>
              </p>
            </div>
            <PublishStrip
              published={published}
              busy={mutating}
              onPublish={handlePublish}
              onUnpublish={handleUnpublish}
              liveUrl={liveUrl}
              justPublishedAt={justPublishedAt}
              noun="strategy"
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
          kind="strategy"
          initialSource={strategy.data?.markdown ?? ''}
          sections={STRATEGY_SECTIONS}
          onSave={handleSave}
          vocabs={{
            ...STATIC_VOCABS,
            themes: (themes.data ?? []).map((t) => ({ key: t.key, label: t.label })),
          }}
          saving={save.isPending}
          validationErrors={validationErrors}
          saveLabel="Save strategy"
        />
      </div>
    </div>
  );
}
