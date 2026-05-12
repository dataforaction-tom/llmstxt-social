/**
 * Smoke test for the idea editor's publish/unpublish controls.
 *
 * Mirrors EditStrategy.test — same mocking + assertion pattern.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import EditIdeaPage from './EditIdea';

const publishMutateAsync = vi.fn(async () => undefined);
const unpublishMutateAsync = vi.fn(async () => undefined);
const saveMutateAsync = vi.fn(async () => undefined);

let mockData: { markdown: string; org_id: string; published: boolean } | null;

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    useIdeaMarkdown: () => ({
      isLoading: false,
      isError: false,
      data: mockData,
      error: null,
    }),
    useSaveIdea: () => ({ mutateAsync: saveMutateAsync, isPending: false }),
    usePublishIdea: () => ({ mutateAsync: publishMutateAsync, isPending: false }),
    useUnpublishIdea: () => ({ mutateAsync: unpublishMutateAsync, isPending: false }),
  };
});

function renderAt(orgId: string, slug: string) {
  return render(
    <MemoryRouter initialEntries={[`/openorg/edit/${orgId}/ideas/${slug}`]}>
      <Routes>
        <Route
          path="/openorg/edit/:orgId/ideas/:slug"
          element={<EditIdeaPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EditIdeaPage publish controls', () => {
  beforeEach(() => {
    publishMutateAsync.mockClear();
    unpublishMutateAsync.mockClear();
    saveMutateAsync.mockClear();
  });

  it('shows Draft badge and Publish button when unpublished', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-idea/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1', 'literacy-pop-up');

    expect(screen.getByLabelText(/idea is a draft/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^publish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^unpublish$/i })).toBeNull();
  });

  it('shows Published badge and Unpublish button when published', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-idea/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1', 'literacy-pop-up');

    expect(screen.getByLabelText(/idea is published/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^unpublish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^publish$/i })).toBeNull();
  });

  it('calls publishIdea when Publish is clicked', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-idea/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1', 'literacy-pop-up');

    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(publishMutateAsync).toHaveBeenCalledTimes(1);
    expect(unpublishMutateAsync).not.toHaveBeenCalled();
  });

  it('calls unpublishIdea when Unpublish is clicked', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-idea/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1', 'literacy-pop-up');

    fireEvent.click(screen.getByRole('button', { name: /^unpublish$/i }));
    expect(unpublishMutateAsync).toHaveBeenCalledTimes(1);
    expect(publishMutateAsync).not.toHaveBeenCalled();
  });
});
