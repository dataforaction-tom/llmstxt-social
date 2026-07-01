/**
 * Smoke test for the public strategy detail page.
 *
 * Mocks the API client to exercise render branches without a real HTTP
 * boundary. Verifies a rich strategy renders priorities / not-doing /
 * tensions, that sparse data degrades gracefully, and that 404 surfaces a
 * "not found" message.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import StrategyDetailPage from './StrategyDetail';

const fetchPublicStrategy = vi.fn();
const fetchPublicStrategyHistory = vi.fn();

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    fetchPublicStrategy: (orgId: string, slug: string) =>
      fetchPublicStrategy(orgId, slug),
    fetchPublicStrategyHistory: (orgId: string, slug: string) =>
      fetchPublicStrategyHistory(orgId, slug),
  };
});

function renderAt(orgId: string, slug: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/openorg/${orgId}/strategies/${slug}`]}>
        <Routes>
          <Route
            path="/openorg/:orgId/strategies/:slug"
            element={<StrategyDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RICH_STRATEGY = {
  title: 'No One Hungry by 2027',
  status: 'active',
  access_level: 'full_public',
  period: { start: '2024', end: '2027', horizon: '3 years' },
  themes: ['food_access', 'community_development'],
  summary: 'Ending food insecurity across the borough.',
  priorities: [
    {
      title: 'Scale the community pantry network',
      maturity: 'developing',
      narrative: 'Grow from 3 to 12 pantries.',
      success_indicators: ['12 pantries open', '5,000 members'],
    },
  ],
  not_doing: [{ title: 'Running a food bank', rationale: 'Others do this well.' }],
  tensions: [
    { title: 'Dignity vs scale', narrative: 'Bigger reach risks impersonal service.' },
  ],
  learning: {
    what_changed: [{ lesson: 'We moved from parcels to choice-based pantries.' }],
  },
  relationships: {
    partnerships: [
      { name: 'FareShare South West', direction: 'established', narrative: 'Surplus food supply.' },
    ],
    ecosystem_position: 'We convene the food-justice network.',
  },
  resource_model: {
    current_funding_mix: { grants: 55, local_authority: 30 },
    sustainability_direction: 'diversifying',
    resourcing_gaps: ['Coordinator role funded only to 2026.'],
  },
};

describe('StrategyDetailPage', () => {
  beforeEach(() => {
    fetchPublicStrategy.mockReset();
    fetchPublicStrategyHistory.mockReset();
    fetchPublicStrategyHistory.mockResolvedValue([]);
  });

  it('renders a rich strategy with its fields', async () => {
    fetchPublicStrategy.mockResolvedValue(RICH_STRATEGY);
    renderAt('GB-CHC-9000001', 'no-one-hungry-2027');

    expect(await screen.findByText('No One Hungry by 2027')).toBeInTheDocument();
    expect(
      screen.getByText('Ending food insecurity across the borough.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Scale the community pantry network')).toBeInTheDocument();
    expect(screen.getByText('Grow from 3 to 12 pantries.')).toBeInTheDocument();
    expect(screen.getByText('12 pantries open')).toBeInTheDocument();
    expect(screen.getByText('Running a food bank')).toBeInTheDocument();
    expect(screen.getByText('Dignity vs scale')).toBeInTheDocument();
    expect(
      screen.getByText('We moved from parcels to choice-based pantries.'),
    ).toBeInTheDocument();
    // structured relationships + resource model
    expect(screen.getByText('FareShare South West')).toBeInTheDocument();
    expect(screen.getByText('Coordinator role funded only to 2026.')).toBeInTheDocument();
    expect(screen.getByText(/55%/)).toBeInTheDocument();

    const rawLink = screen.getByRole('link', { name: /raw json/i });
    expect(rawLink).toHaveAttribute(
      'href',
      '/open-org/GB-CHC-9000001/strategies/no-one-hungry-2027.json',
    );
  });

  it('degrades gracefully for a sparse strategy', async () => {
    fetchPublicStrategy.mockResolvedValue({
      title: 'Learning for All',
      summary: 'Every child reading at age level.',
    });
    renderAt('GB-CHC-9000004', 'learning-for-all-2029');

    expect(await screen.findByText('Learning for All')).toBeInTheDocument();
    expect(
      screen.getByText('Every child reading at age level.'),
    ).toBeInTheDocument();
  });

  it('shows a not-found message on 404', async () => {
    fetchPublicStrategy.mockRejectedValue(new Error('Not Found'));
    renderAt('GB-CHC-9000001', 'missing');

    await waitFor(() =>
      expect(screen.getByText(/not found/i)).toBeInTheDocument(),
    );
  });
});
