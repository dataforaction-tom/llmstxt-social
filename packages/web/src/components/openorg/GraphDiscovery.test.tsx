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
      cluster_id: 1,
    },
    {
      id: 'idea:GB-CHC-1:kitchen',
      type: 'idea',
      name: 'Community Kitchen',
      themes: ['food_access'],
      org_id: 'GB-CHC-1',
      cost_range: [80000, 120000],
      summary: 'A community kitchen serving hot meals.',
      place: 'Great Yarmouth',
      connections: [
        { org_name: 'Beta', org_id: 'GB-CHC-2', relationship: 'complementary' },
      ],
      cluster_id: 1,
    },
    {
      id: 'strategy:GB-CHC-1:2025-2028',
      type: 'strategy',
      name: '2025-2028 Strategy',
      themes: ['food_access'],
      org_id: 'GB-CHC-1',
      summary: 'Three-year plan for food access.',
      period: { start: '2025-01-01', end: '2028-12-31', horizon: '3_5_years' },
      priorities_count: 4,
      cluster_id: 1,
    },
    {
      id: 'GB-CHC-2',
      type: 'organisation',
      name: 'Beta Trust',
      themes: ['food_access'],
      area: 'Great Yarmouth',
      income_band: '100k-250k',
      ideas_count: 0,
      strategy_themes: [],
      cluster_id: 1,
    },
    {
      id: 'GB-CHC-99',
      type: 'organisation',
      name: 'Lone Org',
      themes: ['education'],
      area: 'Nowhere',
      income_band: '10k-100k',
      ideas_count: 0,
      strategy_themes: [],
      cluster_id: null,
    },
  ],
  edges: [
    { source: 'GB-CHC-1', target: 'idea:GB-CHC-1:kitchen', type: 'org_idea' },
    { source: 'GB-CHC-1', target: 'strategy:GB-CHC-1:2025-2028', type: 'org_strategy' },
    { source: 'GB-CHC-1', target: 'GB-CHC-2', type: 'shared_theme', weight: 2 },
    {
      source: 'strategy:GB-CHC-1:2025-2028',
      target: 'idea:GB-CHC-1:kitchen',
      type: 'strategy_idea',
    },
    {
      source: 'idea:GB-CHC-1:kitchen',
      target: 'GB-CHC-2',
      type: 'idea_org_connection',
      relationship: 'complementary',
    },
  ],
  graph_summary: {
    total_nodes: 5,
    total_edges: 5,
    organisations: 3,
    ideas: 1,
    strategies: 1,
    clusters: [
      {
        description:
          '2 organisations (Riverside Trust, Beta Trust) and 1 idea around food_access, health in Great Yarmouth',
        themes: ['food_access', 'health'],
        node_count: 4,
        org_names: ['Riverside Trust', 'Beta Trust'],
        ideas_summary: 'A community kitchen serving hot meals.',
        places: ['Great Yarmouth'],
        dominant_themes: ['food_access', 'health'],
        edge_count: 5,
      },
    ],
  },
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

  it('renders new semantic edge types with their stroke colours', () => {
    const { container } = renderComponent();
    const lines = container.querySelectorAll('svg line[data-edge-type]');
    const types = new Set(Array.from(lines).map((l) => l.getAttribute('data-edge-type')));
    expect(types.has('strategy_idea')).toBe(true);
    expect(types.has('idea_org_connection')).toBe(true);
  });

  it('renders arrowhead markers for directed edges', () => {
    const { container } = renderComponent();
    // SVG marker definitions should exist
    const marker = container.querySelector('svg defs marker');
    expect(marker).not.toBeNull();
    // Directed edge lines should reference the marker
    const directedLines = container.querySelectorAll('svg line[data-edge-type="strategy_idea"]');
    expect(directedLines.length).toBeGreaterThan(0);
    const markerEnd = directedLines[0].getAttribute('marker-end');
    expect(markerEnd).toBeTruthy();
  });

  it('shows the cluster summary panel with total counts when present', () => {
    renderComponent();
    const counts = screen.getByTestId('landscape-counts');
    expect(counts.textContent).toMatch(/3 organisations, 1 idea, 1 strategy/i);
  });

  it('renders a cluster card with the description sentence and dominant theme chips', () => {
    renderComponent();
    const cards = screen.getAllByTestId('cluster-card');
    expect(cards.length).toBeGreaterThanOrEqual(1);
    // Description includes the named orgs.
    expect(cards[0].textContent).toContain('Riverside Trust');
    expect(cards[0].textContent).toContain('Great Yarmouth');
    // Dominant themes render as chips.
    const chips = cards[0].querySelectorAll('[data-cluster-theme-chip]');
    expect(chips.length).toBe(2);
  });

  it('clicking a cluster card dims nodes outside the cluster', () => {
    const { container } = renderComponent();
    const card = screen.getByTestId('cluster-card');
    fireEvent.click(card);
    // The lone org (cluster_id null) should now be dimmed.
    const loneCircle = container.querySelector('svg circle[data-id="GB-CHC-99"]');
    expect(loneCircle).not.toBeNull();
    expect(loneCircle!.getAttribute('opacity')).toBe('0.25');
    // A clustered node stays full opacity.
    const clusteredCircle = container.querySelector('svg circle[data-id="GB-CHC-1"]');
    expect(clusteredCircle!.getAttribute('opacity')).not.toBe('0.25');
  });

  it('renders zoom + fit + reset view controls', () => {
    renderComponent();
    expect(screen.getByRole('button', { name: /zoom in/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /zoom out/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fit to view/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset view/i })).toBeInTheDocument();
  });

  it('tags nodes as draggable targets via data-node', () => {
    const { container } = renderComponent();
    const draggable = container.querySelector('g[data-node="GB-CHC-1"]');
    expect(draggable).not.toBeNull();
  });

  it('renders the Clusters toggle button, off by default', () => {
    renderComponent();
    const toggle = screen.getByRole('button', { name: /clusters/i });
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
  });

  it('turning the Clusters toggle on colour-codes nodes by cluster instead of type', () => {
    const { container } = renderComponent();
    const toggle = screen.getByRole('button', { name: /clusters/i });
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    // Cluster 1 nodes should share the same fill colour.
    const c1 = container.querySelector('svg circle[data-id="GB-CHC-1"]');
    const c2 = container.querySelector('svg circle[data-id="GB-CHC-2"]');
    expect(c1!.getAttribute('fill')).toBeTruthy();
    expect(c1!.getAttribute('fill')).toBe(c2!.getAttribute('fill'));
    // The unclustered node should use the type-based colour.
    const lone = container.querySelector('svg circle[data-id="GB-CHC-99"]');
    expect(lone!.getAttribute('fill')).not.toBe(c1!.getAttribute('fill'));
  });

  it('shows a "No clusters" message when only isolated nodes exist', () => {
    graphDataValue = {
      nodes: [
        { id: 'GB-CHC-1', type: 'organisation', name: 'Solo', themes: ['education'], cluster_id: null },
        { id: 'GB-CHC-2', type: 'organisation', name: 'Other', themes: ['health'], cluster_id: null },
      ],
      edges: [],
      graph_summary: {
        total_nodes: 2,
        total_edges: 0,
        organisations: 2,
        ideas: 0,
        strategies: 0,
        clusters: [],
      },
    };
    renderComponent();
    expect(screen.getByText(/no clusters/i)).toBeInTheDocument();
  });

  it('idea side panel shows summary, themes, place, cost range, and connections', () => {
    const { container } = renderComponent();
    const ideaCircle = container.querySelector('svg circle[data-id="idea:GB-CHC-1:kitchen"]');
    expect(ideaCircle).not.toBeNull();
    fireEvent.click(ideaCircle!);
    const aside = container.querySelector('aside')!;
    expect(aside.textContent).toContain('A community kitchen serving hot meals.');
    expect(aside.textContent).toContain('Great Yarmouth');
    expect(aside.textContent).toContain('£80,000');
    // Connection list shows org name + relationship
    expect(aside.textContent).toContain('Beta');
    expect(aside.textContent).toContain('complementary');
  });

  it('strategy side panel shows summary, period, and priorities count', () => {
    const { container } = renderComponent();
    const stratCircle = container.querySelector('svg circle[data-id="strategy:GB-CHC-1:2025-2028"]');
    expect(stratCircle).not.toBeNull();
    fireEvent.click(stratCircle!);
    const aside = container.querySelector('aside')!;
    expect(aside.textContent).toContain('Three-year plan for food access.');
    expect(aside.textContent).toContain('2025-01-01');
    expect(aside.textContent).toContain('4 priorities');
  });

  it('idea node side panel has a link to the idea detail page', () => {
    const { container } = renderComponent();
    const ideaCircle = container.querySelector('svg circle[data-id="idea:GB-CHC-1:kitchen"]');
    fireEvent.click(ideaCircle!);
    const ideaLink = screen.getByRole('link', { name: /view idea/i });
    expect(ideaLink).toHaveAttribute('href', '/openorg/GB-CHC-1/ideas/kitchen');
  });

  it('strategy node side panel has a link to the strategy detail page', () => {
    const { container } = renderComponent();
    const stratCircle = container.querySelector('svg circle[data-id="strategy:GB-CHC-1:2025-2028"]');
    fireEvent.click(stratCircle!);
    const stratLink = screen.getByRole('link', { name: /view strategy/i });
    expect(stratLink).toHaveAttribute(
      'href',
      '/openorg/GB-CHC-1/strategies/2025-2028',
    );
  });

  it('filter toggle button is present and starts off', () => {
    renderComponent();
    const toggle = screen.getByRole('button', { name: /show only explicit connections/i });
    expect(toggle).toBeInTheDocument();
    // Off by default — no 'active-only' indicator class
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
  });

  it('clicking the filter toggle hides derived edges and shows only explicit ones', () => {
    const { container } = renderComponent();
    // Initially shared_theme (derived) is visible
    const beforeTypes = new Set(
      Array.from(container.querySelectorAll('svg line[data-edge-type]')).map((l) =>
        l.getAttribute('data-edge-type'),
      ),
    );
    expect(beforeTypes.has('shared_theme')).toBe(true);

    const toggle = screen.getByRole('button', { name: /show only explicit connections/i });
    fireEvent.click(toggle);

    const afterLines = container.querySelectorAll('svg line[data-edge-type]');
    const afterTypes = new Set(Array.from(afterLines).map((l) => l.getAttribute('data-edge-type')));
    // Derived edges hidden
    expect(afterTypes.has('shared_theme')).toBe(false);
    // Explicit edges still shown
    expect(afterTypes.has('org_idea')).toBe(true);
    expect(afterTypes.has('strategy_idea')).toBe(true);
    expect(afterTypes.has('idea_org_connection')).toBe(true);
  });

  it('edge label appears on hover for edges with a relationship or description', () => {
    const { container } = renderComponent();
    const edgeLine = container.querySelector('svg line[data-edge-type="idea_org_connection"]');
    expect(edgeLine).not.toBeNull();
    fireEvent.mouseEnter(edgeLine!);
    // A label text element should appear near the edge
    const edgeLabels = container.querySelectorAll('svg text[data-edge-label]');
    expect(edgeLabels.length).toBeGreaterThan(0);
    expect(Array.from(edgeLabels).some((l) => l.textContent?.includes('complementary'))).toBe(true);
  });

  it('does not crash when the API returns an unknown edge type (forward-compat)', () => {
    // Version skew: the backend can ship a new semantic edge type before the
    // frontend bundle knows about it. An unknown type must degrade gracefully
    // (edge skipped) rather than throwing on EDGE_STROKE[type].stroke.
    graphDataValue = {
      ...mockGraphData,
      edges: [
        ...mockGraphData.edges,
        {
          source: 'GB-CHC-1',
          target: 'GB-CHC-2',
          // a type not present in EDGE_STROKE
          type: 'future_edge_type' as never,
        },
      ],
    };
    const { container } = renderComponent();
    // Renders without throwing; known edges still present, unknown one skipped.
    expect(container.querySelector('svg')).toBeInTheDocument();
    const types = new Set(
      Array.from(container.querySelectorAll('svg line[data-edge-type]')).map((l) =>
        l.getAttribute('data-edge-type'),
      ),
    );
    expect(types.has('org_idea')).toBe(true);
    expect(types.has('future_edge_type')).toBe(false);
  });

  it('legend shows all edge type swatches', () => {
    renderComponent();
    const legend = screen.getByTestId('graph-legend');
    const legendText = legend.textContent ?? '';
    // Should mention derived + explicit edge categories
    expect(legendText).toMatch(/shared theme|theme overlap/i);
    expect(legendText).toMatch(/strategy.*idea/i);
    expect(legendText).toMatch(/idea.*org/i);
  });
});