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
const fetchPublicOrgHistory = vi.fn();

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    fetchPublicProfile: (orgId: string) => fetchPublicProfile(orgId),
    fetchPublicStrategies: (orgId: string) => fetchPublicStrategies(orgId),
    fetchPublicIdeas: (orgId: string) => fetchPublicIdeas(orgId),
    fetchPublicOrgHistory: (orgId: string) => fetchPublicOrgHistory(orgId),
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
  evidence: [
    {
      evidence_id: 'eval-2024',
      title: 'Annual Evaluation',
      description: 'We evaluated the befriending programme across three sites.',
      evidence_type: 'evaluation',
      date: '2024-06-01',
      url: 'https://riverside.example/eval-2024.pdf',
      themes: ['food_access', 'social_prescribing'],
      outcomes: ['500 meals served per month', '40% reduction in loneliness scores'],
    },
    {
      evidence_id: 'case-001',
      title: 'Kitchen case study',
      evidence_type: 'case_study',
      date: '2024-03-15',
      outcomes: ['80% retention'],
    },
  ],
};

describe('ProfileDetailPage', () => {
  beforeEach(() => {
    fetchPublicProfile.mockReset();
    fetchPublicStrategies.mockReset();
    fetchPublicIdeas.mockReset();
    fetchPublicOrgHistory.mockReset();
    fetchPublicStrategies.mockResolvedValue([]);
    fetchPublicIdeas.mockResolvedValue([]);
    fetchPublicOrgHistory.mockResolvedValue([]);
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
    expect(screen.getAllByText('kitchen-network').length).toBeGreaterThan(0);
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

  it('renders a timeline of version events when history is present', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    fetchPublicOrgHistory.mockResolvedValue([
      {
        timestamp: '2026-06-15T09:00:00',
        parent_kind: 'strategy',
        parent_slug: '2025-2028',
        summary: 'Three-year plan to grow community kitchens.',
      },
      {
        timestamp: '2026-05-10T14:30:00',
        parent_kind: 'profile',
        parent_slug: null,
        summary: 'Profile generated from charity number 1234567.',
      },
    ]);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText(/Timeline/i)).toBeInTheDocument();
    });
    expect(screen.getByText('Strategy published')).toBeInTheDocument();
    expect(
      screen.getByText('Profile generated from charity number 1234567.'),
    ).toBeInTheDocument();
  });

  it('does not render a timeline section when there is no history', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    fetchPublicOrgHistory.mockResolvedValue([]);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Riverside Community Trust')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Timeline/i)).not.toBeInTheDocument();
  });

  it('renders idea status badges and created/updated timestamps', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    fetchPublicIdeas.mockResolvedValue([
      {
        slug: 'kitchen-network',
        themes: ['food_access'],
        status: 'developing',
        created_at: '2026-04-01T10:00:00',
        updated_at: '2026-06-01T12:00:00',
      },
    ]);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getAllByText('kitchen-network').length).toBeGreaterThan(0);
    });
    const badge = screen.getByText('developing');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('text-teal');
    expect(screen.getByText(/created/i)).toHaveTextContent('1 Apr 2026');
    expect(screen.getByText(/updated/i)).toHaveTextContent('1 Jun 2026');
  });

  it('renders strategy status badges with correct colours', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    fetchPublicStrategies.mockResolvedValue([
      {
        slug: '2025-2028',
        themes: ['food_access'],
        status: 'active',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-03-01T00:00:00',
      },
    ]);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('2025-2028')).toBeInTheDocument();
    });
    const badge = screen.getByText('active');
    expect(badge.className).toContain('text-teal');
  });

  // --- evidence section ----------------------------------------------------

  it('renders evidence items when present', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Annual Evaluation')).toBeInTheDocument();
    });
    expect(screen.getByText('Kitchen case study')).toBeInTheDocument();
    expect(
      screen.getByText('We evaluated the befriending programme across three sites.'),
    ).toBeInTheDocument();
    expect(screen.getByText('food_access')).toBeInTheDocument();
    expect(screen.getByText('500 meals served per month')).toBeInTheDocument();
    expect(screen.getByText('40% reduction in loneliness scores')).toBeInTheDocument();
  });

  it('shows a link for evidence items with a URL', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Annual Evaluation')).toBeInTheDocument();
    });
    const link = screen.getByText('View evidence →').closest('a');
    expect(link).toHaveAttribute('href', 'https://riverside.example/eval-2024.pdf');
  });

  it('does not show a link for evidence items without a URL', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Kitchen case study')).toBeInTheDocument();
    });
    // Only one evidence item has a URL (eval-2024), so only one "View evidence →" link.
    const links = screen.getAllByText('View evidence →');
    expect(links).toHaveLength(1);
  });

  it('renders evidence type badge with correct colour class', async () => {
    fetchPublicProfile.mockResolvedValue(FULL_PROFILE);
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Annual Evaluation')).toBeInTheDocument();
    });
    const badges = screen.getAllByTestId('evidence-type-badge');
    // eval-2024 → evaluation → teal
    expect(badges[0].className).toContain('text-teal');
    // case-001 → case_study → coral
    expect(badges[1].className).toContain('text-coral');
  });

  it('does not render an Evidence section when no evidence items', async () => {
    fetchPublicProfile.mockResolvedValue({
      ...FULL_PROFILE,
      evidence: [],
    });
    renderAt('GB-CHC-1');

    await waitFor(() => {
      expect(screen.getByText('Riverside Community Trust')).toBeInTheDocument();
    });
    // "Evidence" kicker should not appear (Evidence summary is renamed separately).
    // The Evidence summary section still shows because FULL_PROFILE has evidence_summary.
    // So we check for absence of the evidence item titles.
    expect(screen.queryByText('Annual Evaluation')).not.toBeInTheDocument();
  });
});
