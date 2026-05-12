/**
 * Smoke test for the public profile detail page.
 *
 * Mocks the API client so we exercise the render branches without spinning
 * up a real QueryClient or HTTP boundary. Verifies that the v0.5 enrichment
 * (programmes, evidence_summary, beneficiaries) renders, and that 404 from
 * the API surfaces a "not found" message rather than a stack trace.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ProfileDetailPage from './ProfileDetail';

const fetchPublicProfile = vi.fn();
const fetchPublicStrategies = vi.fn();
const fetchPublicIdeas = vi.fn();

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    fetchPublicProfile: (orgId: string) => fetchPublicProfile(orgId),
    fetchPublicStrategies: (orgId: string) => fetchPublicStrategies(orgId),
    fetchPublicIdeas: (orgId: string) => fetchPublicIdeas(orgId),
  };
});

function renderAt(orgId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/openorg/${orgId}`]}>
        <Routes>
          <Route path="/openorg/:orgId" element={<ProfileDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const FULL_PROFILE = {
  identity: {
    name: 'Riverside Community Trust',
    also_known_as: ['Riverside CT'],
    geography: { primary_area: 'Great Yarmouth' },
    website: 'https://riverside.example',
    contact: { email: 'hello@riverside.example', phone: '01493 000000' },
  },
  mission: {
    summary: 'Supporting isolated older people in Great Yarmouth.',
    themes: ['older_people', 'loneliness'],
    theory_of_change: 'We rebuild touchpoints in community life.',
    beneficiaries: ['Isolated older people'],
    programmes: [
      {
        name: 'Community kitchen',
        description: 'Daily meals cooked together.',
        eligibility: 'Anyone 65+',
      },
    ],
    evidence_summary: {
      beneficiaries_served_text: '200 people per week',
      outcomes: ['85% report improved wellbeing'],
    },
  },
};

describe('ProfileDetailPage', () => {
  beforeEach(() => {
    fetchPublicProfile.mockReset();
    fetchPublicStrategies.mockReset();
    fetchPublicIdeas.mockReset();
    fetchPublicStrategies.mockResolvedValue([]);
    fetchPublicIdeas.mockResolvedValue([]);
  });

  it('renders mission, themes, programmes, evidence', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1234567');

    await waitFor(() => {
      expect(screen.getByText('Riverside Community Trust')).toBeInTheDocument();
    });
    expect(
      screen.getByText('Supporting isolated older people in Great Yarmouth.'),
    ).toBeInTheDocument();
    expect(screen.getByText('older_people')).toBeInTheDocument();
    expect(screen.getByText('Community kitchen')).toBeInTheDocument();
    expect(screen.getByText('200 people per week')).toBeInTheDocument();
    expect(screen.getByText(/85% report improved wellbeing/)).toBeInTheDocument();
    expect(screen.getByText('Isolated older people')).toBeInTheDocument();
    expect(screen.getByText(/Also known as: Riverside CT/)).toBeInTheDocument();
  });

  it('renders strategies and ideas when present', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    fetchPublicStrategies.mockResolvedValue([
      { slug: '2025-2028', themes: ['food_access'], status: 'active', summary: 'Plan.' },
    ]);
    fetchPublicIdeas.mockResolvedValue([
      { slug: 'kitchen-network', themes: ['food_access'], status: 'developing' },
    ]);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('2025-2028')).toBeInTheDocument();
    });
    expect(screen.getByText('kitchen-network')).toBeInTheDocument();
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it('surfaces a not-found message when the API 404s', async () => {
    fetchPublicProfile.mockRejectedValue(new Error('404'));
    renderAt('GB-CHC-NONE');

    await waitFor(() => {
      expect(screen.getByText(/profile not found/i)).toBeInTheDocument();
    });
  });

  it('links to raw JSON for power users', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1234567');

    await waitFor(() => {
      const rawLink = screen.getByText('View raw JSON').closest('a');
      expect(rawLink).toHaveAttribute('href', '/open-org/GB-CHC-1234567/profile.json');
    });
  });
});
