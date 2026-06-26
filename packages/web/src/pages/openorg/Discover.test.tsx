/**
 * Tests for the ideas-first Discover page.
 *
 * The Discover page defaults to the Ideas view, shows a hero summary of the
 * ideas landscape, and lets funders filter by theme chips. Leaflet is mocked
 * out (it touches `window` at import time) so we only exercise the ideas surface.
 */

import { afterEach, describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HelmetProvider } from 'react-helmet-async';

import DiscoverPage from './Discover';
import type { IdeaPage, IdeasSummary, ThemeEntry } from '../../api/openorg';

// Stub Leaflet before the Discover page imports it — the real module touches
// `window` at import time and breaks under happy-dom.
vi.mock('leaflet', () => ({
  default: { Icon: { Default: { mergeOptions: () => {} } } },
  Icon: { Default: { mergeOptions: () => {} } },
}));
vi.mock('react-leaflet', () => ({
  MapContainer: () => null,
  Marker: () => null,
  Popup: () => null,
  TileLayer: () => null,
}));
vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet/dist/images/marker-icon.png', () => ({ default: 'marker-icon.png' }));
vi.mock('leaflet/dist/images/marker-icon-2x.png', () => ({ default: 'marker-icon-2x.png' }));
vi.mock('leaflet/dist/images/marker-shadow.png', () => ({ default: 'marker-shadow.png' }));
vi.mock('./discoverGeo', () => ({ hasValidGeolocation: () => false }));

const mockThemes: ThemeEntry[] = [
  { key: 'food_access', label: 'Food Access', description: '' },
  { key: 'education', label: 'Education', description: '' },
  { key: 'health', label: 'Health', description: '' },
];

const mockSummary: IdeasSummary = {
  total_ideas: 42,
  total_orgs: 18,
  themes_breakdown: { food_access: 12, education: 10, health: 8 },
  status_breakdown: { seed: 5, developing: 20, shaped: 10, delivered: 7 },
};

const mockIdeasPage: IdeaPage = {
  results: [
    {
      org_id: 'GB-CHC-1',
      org_name: 'Riverside Trust',
      slug: 'kitchen-network',
      summary: 'Three community kitchens.',
      themes: ['food_access'],
      status: 'developing',
      primary_area: 'Great Yarmouth',
      cost_lower: 80000,
      cost_upper: 120000,
      cost_currency: 'GBP',
      idea_url: '/open-org/GB-CHC-1/ideas/kitchen-network.json',
      profile_url: '/openorg/GB-CHC-1',
      signal_count: 3,
    },
    {
      org_id: 'GB-CHC-2',
      org_name: 'Age UK Norfolk',
      slug: 'warm-hubs',
      summary: 'Warm hubs for older people.',
      themes: ['health', 'education'],
      status: 'seed',
      primary_area: 'Norwich',
      cost_lower: null,
      cost_upper: null,
      cost_currency: null,
      idea_url: '/open-org/GB-CHC-2/ideas/warm-hubs.json',
      profile_url: '/openorg/GB-CHC-2',
      signal_count: 0,
    },
  ],
  next_cursor: null,
};

let ideasPageValue: IdeaPage | undefined;
let summaryValue: IdeasSummary | undefined;
let themesValue: ThemeEntry[] | undefined;

// Cache the filtered page object per theme so the mock returns a STABLE
// reference across re-renders. The real useIdeasFirstPage (React Query) does
// this; without it, a fresh object each render trips Discover's
// useEffect([firstPage.data]) into an infinite render loop. Cleared per test.
const ideasPageCache = new Map<string, IdeaPage>();

// Stable empty page for the Organisations view's useDiscoveryFirstPage mock.
const emptyDiscoveryPage = { results: [], next_cursor: null };

vi.mock('../../api/openorg', () => ({
  useThemes: () => ({ data: themesValue }),
  useIdeasSummary: () => ({ data: summaryValue, isLoading: false, isError: false }),
  useIdeasFirstPage: (filters: { theme?: string }) => {
    const key = filters?.theme ?? '';
    if (!ideasPageCache.has(key)) {
      ideasPageCache.set(key, {
        results: (ideasPageValue?.results ?? []).filter(
          (r: { themes: string[] }) => !filters?.theme || r.themes.includes(filters.theme),
        ),
        next_cursor: null,
      });
    }
    return {
      data: ideasPageCache.get(key),
      isLoading: false,
      isError: false,
      isFetching: false,
    };
  },
  useDiscoveryFirstPage: () => ({
    // Stable reference (see ideasPageCache note) — the Organisations view's
    // useEffect([firstPage.data]) would otherwise loop infinitely in tests.
    data: emptyDiscoveryPage,
    isLoading: false,
    isError: false,
    isFetching: false,
  }),
  fetchDiscoveryPage: vi.fn(),
  fetchIdeasPage: vi.fn(),
}));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <HelmetProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <DiscoverPage />
        </MemoryRouter>
      </QueryClientProvider>
    </HelmetProvider>,
  );
}

describe('Discover page — ideas-first', () => {
  beforeEach(() => {
    themesValue = mockThemes;
    summaryValue = mockSummary;
    ideasPageValue = mockIdeasPage;
    ideasPageCache.clear();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('defaults to the Ideas view (not Organisations or Graph)', () => {
    renderPage();
    // The Ideas button should be the active (pressed) view.
    const ideasButton = screen.getByRole('button', { name: /^ideas$/i });
    expect(ideasButton).toBeInTheDocument();
    // The ideas landscape section should be present.
    expect(screen.getByTestId('ideas-landscape')).toBeInTheDocument();
  });

  it('shows the hero summary counts (N ideas from M organisations across K themes)', () => {
    renderPage();
    const summary = screen.getByTestId('ideas-summary');
    expect(summary.textContent).toMatch(/42/); // ideas
    expect(summary.textContent).toMatch(/18/); // orgs
    expect(summary.textContent).toMatch(/3/); // themes (3 distinct)
  });

  it('renders theme chips with counts from the summary', () => {
    renderPage();
    const foodChip = screen.getByText('Food Access');
    expect(foodChip).toBeInTheDocument();
    // The count is rendered in a sibling span with data-theme-count.
    const chip = foodChip.closest('button');
    expect(chip).not.toBeNull();
    const count = chip!.querySelector('[data-theme-count]');
    expect(count?.textContent).toBe('12');
  });

  it('clicking a theme chip filters ideas to that theme', async () => {
    renderPage();
    // Initially both ideas are visible.
    expect(screen.getByText('kitchen-network')).toBeInTheDocument();
    expect(screen.getByText('warm-hubs')).toBeInTheDocument();

    // Click the Education chip — only warm-hubs has education.
    fireEvent.click(screen.getByText('Education'));

    // After filtering, only warm-hubs should remain (kitchen-network has only
    // food_access). We use waitFor because the client-side filter re-renders.
    await waitFor(() => {
      expect(screen.queryByText('kitchen-network')).not.toBeInTheDocument();
      expect(screen.getByText('warm-hubs')).toBeInTheDocument();
    });
  });

  it('clicking a theme chip again deselects it and restores all ideas', async () => {
    renderPage();
    fireEvent.click(screen.getByText('Food Access'));
    await waitFor(() => {
      expect(screen.getByText('kitchen-network')).toBeInTheDocument();
      expect(screen.queryByText('warm-hubs')).not.toBeInTheDocument();
    });
    // Click again to deselect.
    fireEvent.click(screen.getByText('Food Access'));
    await waitFor(() => {
      expect(screen.getByText('kitchen-network')).toBeInTheDocument();
      expect(screen.getByText('warm-hubs')).toBeInTheDocument();
    });
  });

  it('renders idea cards with title, org, status, and signal count', () => {
    const { container } = renderPage();
    // The first idea card — the component tags cards with data-idea-card.
    const card = container.querySelector<HTMLElement>(
      '[data-idea-card="GB-CHC-1-kitchen-network"]',
    );
    expect(card).not.toBeNull();
    expect(card!.textContent).toContain('kitchen-network');
    expect(card!.textContent).toContain('Riverside Trust');
    expect(card!.textContent).toContain('developing');
    expect(card!.textContent).toContain('3 interested');
  });

  it('switching to Organisations view hides the ideas landscape', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /organisations/i }));
    expect(screen.queryByTestId('ideas-landscape')).not.toBeInTheDocument();
  });
});