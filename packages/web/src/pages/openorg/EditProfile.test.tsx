/**
 * Integration smoke test for the profile editor's publish/unpublish controls.
 *
 * Mocks the API-client hooks so we exercise the page's branching without a
 * real QueryClient or HTTP boundary. Focuses on the user-visible contract:
 * which badge renders, which button renders, and that the right mutation
 * fires on click.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import EditProfilePage from './EditProfile';

const publishMutateAsync = vi.fn(async () => undefined);
const unpublishMutateAsync = vi.fn(async () => undefined);
const saveMutateAsync = vi.fn(async () => undefined);

let mockProfileData: { markdown: string; org_id: string; published: boolean } | null;

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    useProfileMarkdown: () => ({
      isLoading: false,
      isError: false,
      data: mockProfileData,
      error: null,
    }),
    useSaveProfile: () => ({ mutateAsync: saveMutateAsync, isPending: false }),
    usePublishProfile: () => ({ mutateAsync: publishMutateAsync, isPending: false }),
    useUnpublishProfile: () => ({ mutateAsync: unpublishMutateAsync, isPending: false }),
    useHistory: () => ({ isLoading: false, isError: false, data: [], error: null }),
    useRestoreVersion: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useThemes: () => ({
      isLoading: false,
      data: [{ key: 'older_people', label: 'Older people', description: '' }],
      error: null,
    }),
  };
});

function renderAt(orgId: string) {
  return render(
    <MemoryRouter initialEntries={[`/openorg/edit/${orgId}/profile`]}>
      <Routes>
        <Route path="/openorg/edit/:orgId/profile" element={<EditProfilePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EditProfilePage publish controls', () => {
  beforeEach(() => {
    publishMutateAsync.mockClear();
    unpublishMutateAsync.mockClear();
    saveMutateAsync.mockClear();
  });

  it('shows Draft badge and Publish button when profile is unpublished', () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');

    expect(screen.getByLabelText(/profile is a draft/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^publish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^unpublish$/i })).toBeNull();
  });

  it('shows Published badge and Unpublish button when profile is published', () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1');

    expect(screen.getByLabelText(/profile is published/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^unpublish$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^publish$/i })).toBeNull();
  });

  it('calls the publish mutation when the Publish button is confirmed', async () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');

    // First click opens the inline confirm strip; second click on the strip's
    // confirm button fires the mutation.
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /^publish$/i }).at(-1)!);
    expect(publishMutateAsync).toHaveBeenCalledTimes(1);
    expect(unpublishMutateAsync).not.toHaveBeenCalled();
  });

  it('calls the unpublish mutation when the Unpublish button is confirmed', async () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: true,
    };
    renderAt('GB-CHC-1');

    fireEvent.click(screen.getByRole('button', { name: /^unpublish$/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /^unpublish$/i }).at(-1)!);
    expect(unpublishMutateAsync).toHaveBeenCalledTimes(1);
    expect(publishMutateAsync).not.toHaveBeenCalled();
  });

  it('renders the guided sidebar by default when source has frontmatter', () => {
    window.localStorage.clear();
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\nidentity:\n  name: A\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');
    expect(screen.getByRole('button', { name: /^identity$/i })).toBeInTheDocument();
  });

  it('renders the inline publish confirm strip on click', () => {
    mockProfileData = {
      org_id: 'GB-CHC-1',
      markdown: '---\nschema_version: open-org/v0.1\n---\n',
      published: false,
    };
    renderAt('GB-CHC-1');
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(screen.getByText(/publish this profile to the federated network/i)).toBeInTheDocument();
  });
});
