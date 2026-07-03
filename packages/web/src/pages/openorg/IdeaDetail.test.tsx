/**
 * Smoke test for the public idea detail page.
 *
 * Mocks the API client so we exercise the render branches without a real HTTP
 * boundary. Verifies that a rich idea renders its fields, that a sparse idea
 * (title + cost only, as in seed data) degrades gracefully, and that 404
 * surfaces a "not found" message.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import IdeaDetailPage from './IdeaDetail';

const fetchPublicIdea = vi.fn();
const fetchPublicIdeaHistory = vi.fn();

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    fetchPublicIdea: (orgId: string, slug: string) => fetchPublicIdea(orgId, slug),
    fetchPublicIdeaHistory: (orgId: string, slug: string) =>
      fetchPublicIdeaHistory(orgId, slug),
    useIdeaSignals: () => ({ data: [] }),
  };
});

function renderAt(orgId: string, slug: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/openorg/${orgId}/ideas/${slug}`]}>
        <Routes>
          <Route
            path="/openorg/:orgId/ideas/:slug"
            element={<IdeaDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const RICH_IDEA = {
  title: 'ESOL Evening Classes',
  status: 'developing',
  summary: 'Evening English classes for new arrivals.',
  detail: 'Two-hour sessions twice a week, run by trained volunteers.',
  themes: ['refugees_and_migration', 'education'],
  place: { description: 'Birmingham city centre' },
  beneficiaries: ['Refugees', 'Recent migrants'],
  indicative_cost: { lower: 12000, upper: 25000, currency: 'GBP', period: 'year' },
  collaborators: [{ org_name: 'City College', role: 'Venue', confirmed: true }],
  connections: [{ org_name: 'Refugee Council', relationship: 'referral_partner' }],
  linked_strategy_id: 'welcome-strategy-2027',
};

describe('IdeaDetailPage', () => {
  beforeEach(() => {
    fetchPublicIdea.mockReset();
    fetchPublicIdeaHistory.mockReset();
    fetchPublicIdeaHistory.mockResolvedValue([]);
  });

  it('renders a rich idea with its fields', async () => {
    fetchPublicIdea.mockResolvedValue(RICH_IDEA);
    renderAt('GB-CHC-9000005', 'esol-evenings');

    expect(await screen.findByText('ESOL Evening Classes')).toBeInTheDocument();
    expect(screen.getByText('Evening English classes for new arrivals.')).toBeInTheDocument();
    expect(
      screen.getByText('Two-hour sessions twice a week, run by trained volunteers.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Birmingham city centre')).toBeInTheDocument();
    expect(screen.getByText('Refugees')).toBeInTheDocument();
    // cost range rendered
    expect(screen.getByText(/12,000/)).toBeInTheDocument();
    expect(screen.getByText(/25,000/)).toBeInTheDocument();
    // collaborator + linked strategy link
    expect(screen.getByText('City College')).toBeInTheDocument();
    const stratLink = screen.getByRole('link', { name: /welcome-strategy-2027/ });
    expect(stratLink).toHaveAttribute(
      'href',
      '/openorg/GB-CHC-9000005/strategies/welcome-strategy-2027',
    );
    // raw JSON escape hatch survives
    const rawLink = screen.getByRole('link', { name: /raw json/i });
    expect(rawLink).toHaveAttribute(
      'href',
      '/open-org/GB-CHC-9000005/ideas/esol-evenings.json',
    );
  });

  it('degrades gracefully for a sparse idea', async () => {
    fetchPublicIdea.mockResolvedValue({
      title: 'Telephone Befriending Scheme',
      indicative_cost: { lower: 6000, upper: 14000 },
    });
    renderAt('GB-CHC-9000007', 'befriending');

    expect(
      await screen.findByText('Telephone Befriending Scheme'),
    ).toBeInTheDocument();
    expect(screen.getByText(/6,000/)).toBeInTheDocument();
  });

  it('shows a not-found message on 404', async () => {
    fetchPublicIdea.mockRejectedValue(new Error('Not Found'));
    renderAt('GB-CHC-9000005', 'missing');

    await waitFor(() =>
      expect(screen.getByText(/not found/i)).toBeInTheDocument(),
    );
  });
});
