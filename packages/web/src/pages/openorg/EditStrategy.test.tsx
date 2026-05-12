/**
 * Smoke test for the strategy editor's publish/unpublish controls.
 *
 * Mocks the API-client hooks so the page's branching is exercised without
 * spinning up a real QueryClient. Focuses on the same user-visible contract
 * EditProfile.test covers: which badge renders, which button renders, and
 * that the right mutation fires on click.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import EditStrategyPage from './EditStrategy';

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
    useStrategyMarkdown: () => ({
      isLoading: false,
      isError: false,
      data: mockData,
      error: null,
    }),
    useSaveStrategy: () => ({ mutateAsync: saveMutateAsync, isPending: false }),
    usePublishStrategy: () => ({ mutateAsync: publishMutateAsync, isPending: false }),
    useUnpublishStrategy: () => ({ mutateAsync: unpublishMutateAsync, isPending: false }),
  };
});

function renderAt(orgId: string, slug: string) {
  return render(
    <MemoryRouter initialEntries={[`/openorg/edit/${orgId}/strategies/${slug}`]}>
      <Routes>
        <Route
          path="/openorg/edit/:orgId/strategies/:slug"
          element={<EditStrategyPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EditStrategyPage publish controls', () => {
  beforeEach(() => {
    publishMutateAsync.mockClear();
    unpublishMutateAsync.mockClear();
    saveMutateAsync.mockClear();
  });

  it('shows Draft badge and Publish button when unpublished', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-strategy/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1', '2025-2028');

    expect(screen.getByLabelText(/strategy is a draft/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^publish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^unpublish$/i })).toBeNull();
  });

  it('shows Published badge and Unpublish button when published', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-strategy/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1', '2025-2028');

    expect(screen.getByLabelText(/strategy is published/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^unpublish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^publish$/i })).toBeNull();
  });

  it('calls publishStrategy when Publish is clicked', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-strategy/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1', '2025-2028');

    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(publishMutateAsync).toHaveBeenCalledTimes(1);
    expect(unpublishMutateAsync).not.toHaveBeenCalled();
  });

  it('calls unpublishStrategy when Unpublish is clicked', () => {
    mockData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org-strategy/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1', '2025-2028');

    fireEvent.click(screen.getByRole('button', { name: /^unpublish$/i }));
    expect(unpublishMutateAsync).toHaveBeenCalledTimes(1);
    expect(publishMutateAsync).not.toHaveBeenCalled();
  });
});
