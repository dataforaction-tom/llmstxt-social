/**
 * Tests for the GraphDiscovery force-directed graph component.
 *
 * happy-dom doesn't provide SVG layout dimensions, so the D3 force simulation
 * runs against a zero-size container — the component is designed to handle
 * that gracefully (nodes still render, just at default positions).
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import GraphDiscovery from './GraphDiscovery';
import type { GraphData, ThemeEntry } from '../../api/openorg';

const mockThemes: ThemeEntry[] = [
  { key: 'food_access', label: 'Food Access', description: '' },
  { key: 'health', label: 'Health', description: '' },
  { key: 'education', label: 'Education', description: '' },
];

const mockGraphData: GraphData = {
  nodes: [
    {
      id: 'GB-CHC-1',
      type: 'organisation',
      name: 'Riverside Trust',
      themes: ['food_access', 'health'],
      area: 'Great Yarmouth',
      income_band: '250k-500k',
      ideas_count: 1,
      strategy_themes: ['food_access'],
    },
    {
      id: 'idea:GB-CHC-1:kitchen',
      type: 'idea',
      name: 'Community Kitchen',
      themes: ['food_access'],
      org_id: 'GB-CHC-1',
      cost_range: [80000, 120000],
    },
    {
      id: 'strategy:GB-CHC-1:2025-2028',
      type: 'strategy',
      name: '2025-2028 Strategy',
      themes: ['food_access'],
      org_id: 'GB-CHC-1',
    },
  ],
  edges: [
    { source: 'GB-CHC-1', target: 'idea:GB-CHC-1:kitchen', type: 'org_idea' },
    { source: 'GB-CHC-1', target: 'strategy:GB-CHC-1:2025-2028', type: 'org_strategy' },
    { source: 'GB-CHC-1', target: 'GB-CHC-2', type: 'shared_theme', weight: 2 },
  ],
};

let graphDataValue: GraphData | undefined;
let themesValue: ThemeEntry[] | undefined;

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    useGraphData: () => ({
      data: graphDataValue,
      isLoading: false,
      isError: false,
    }),
    useThemes: () => ({ data: themesValue }),
  };
});

function renderComponent() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <GraphDiscovery />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GraphDiscovery', () => {
  beforeEach(() => {
    graphDataValue = mockGraphData;
    themesValue = mockThemes;
  });

  it('renders without crashing', () => {
    const { container } = renderComponent();
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('renders nodes from mock data', () => {
    const { container } = renderComponent();
    const texts = container.querySelectorAll('svg text');
    const labels = Array.from(texts).map((t) => t.textContent);
    expect(labels).toContain('Riverside Trust');
  });

  it('clicking a node shows the side panel with entity name', () => {
    const { container } = renderComponent();
    const orgCircle = container.querySelector('svg circle[data-id="GB-CHC-1"]');
    expect(orgCircle).not.toBeNull();
    fireEvent.click(orgCircle!);
    // The side panel heading should show the org name
    const panelHeading = container.querySelector('aside h3');
    expect(panelHeading).not.toBeNull();
    expect(panelHeading!.textContent).toBe('Riverside Trust');
  });

  it('theme filter checkboxes are present', () => {
    renderComponent();
    expect(screen.getByLabelText(/food access/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/health/i)).toBeInTheDocument();
  });

  it('shows a link to the detail page when an organisation node is selected', () => {
    const { container } = renderComponent();
    const circle = container.querySelector('svg circle[data-id="GB-CHC-1"]');
    expect(circle).not.toBeNull();
    fireEvent.click(circle!);
    const link = screen.getByRole('link', { name: /view profile/i });
    expect(link).toHaveAttribute('href', '/openorg/GB-CHC-1');
  });
});