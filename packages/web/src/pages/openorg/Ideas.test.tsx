/**
 * Smoke test for the cross-org idea browser. Mocks the React Query hooks.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import IdeasPage from './Ideas';

const fetchIdeasPage = vi.fn();
let mockFirstPageData: { results: unknown[]; next_cursor: string | null } | null;
let mockFirstPageIsError = false;

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    fetchIdeasPage: (...args: unknown[]) => fetchIdeasPage(...args),
    useIdeasFirstPage: (filters: unknown) => {
      // Capture the filters the page is asking for so tests can assert.
      fetchIdeasPage(filters, null, 20);
      return {
        isLoading: false,
        isError: mockFirstPageIsError,
        data: mockFirstPageData,
        error: null,
      };
    },
    useThemes: () => ({
      isLoading: false,
      isError: false,
      data: [{ key: 'food_access', label: 'Food access', description: '' }],
    }),
  };
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/openorg/ideas']}>
        <Routes>
          <Route path="/openorg/ideas" element={<IdeasPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SAMPLE_RESULTS = {
  results: [
    {
      org_id: 'GB-CHC-1',
      org_name: 'Riverside Trust',
      slug: 'kitchen-network',
      summary: 'Three community kitchens across Great Yarmouth.',
      themes: ['food_access', 'community_development'],
      status: 'developing',
      primary_area: 'Great Yarmouth',
      cost_lower: 80000,
      cost_upper: 120000,
      cost_currency: 'GBP',
      idea_url: '/open-org/GB-CHC-1/ideas/kitchen-network.json',
      profile_url: '/openorg/GB-CHC-1',
    },
  ],
  next_cursor: null,
};

describe('IdeasPage', () => {
  beforeEach(() => {
    fetchIdeasPage.mockReset();
    mockFirstPageIsError = false;
    mockFirstPageData = SAMPLE_RESULTS;
  });

  it('renders ideas with org name + cost range', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('kitchen-network')).toBeInTheDocument();
    });
    expect(screen.getByText('Riverside Trust')).toBeInTheDocument();
    expect(screen.getByText(/Three community kitchens/)).toBeInTheDocument();
    expect(screen.getByText(/GBP 80,000/)).toBeInTheDocument();
    // The result row renders the status inside a span with this exact class;
    // the option dropdown also contains "Developing" but with different
    // capitalisation and a different element.
    expect(
      screen.getByText('developing', { selector: 'span' }),
    ).toBeInTheDocument();
  });

  it('shows empty-state when no matches', async () => {
    mockFirstPageData = { results: [], next_cursor: null };
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/No matches/i)).toBeInTheDocument();
    });
  });

  it('Apply button re-renders the hook with the chosen status filter', async () => {
    mockFirstPageData = { results: [], next_cursor: null };
    renderPage();

    const initialCallCount = fetchIdeasPage.mock.calls.length;

    const statusSelect = screen.getByLabelText(/Status/i) as HTMLSelectElement;
    fireEvent.change(statusSelect, { target: { value: 'active' } });
    fireEvent.click(screen.getByRole('button', { name: /^Apply$/i }));

    await waitFor(() => {
      expect(fetchIdeasPage.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
    const lastCall = fetchIdeasPage.mock.calls[fetchIdeasPage.mock.calls.length - 1];
    expect(lastCall[0]).toMatchObject({ status: 'active' });
  });
});
