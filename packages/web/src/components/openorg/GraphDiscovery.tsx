/**
 * GraphDiscovery — force-directed graph visualisation for Open Org discovery.
 *
 * Uses d3-force for layout and renders SVG via React. Nodes are coloured by
 * type (organisation / idea / strategy), sized by income band or cost range.
 * Edges show ownership, shared themes/areas, and the semantic connection
 * layer (strategy→idea, idea→idea shared theme/place, idea→org explicit
 * connections, strategy→strategy shared themes). Supports hover highlighting
 * with edge labels, click-to-detail-panel, zoom/pan, theme filter checkboxes,
 * and an "explicit only" toggle that hides derived edges.
 */

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { Link } from 'react-router-dom';
import * as d3 from 'd3';
import {
  type GraphData,
  type GraphEdge,
  type GraphNode,
  type ThemeEntry,
  useGraphData,
  useThemes,
} from '../../api/openorg';

// --- colour + size constants ----------------------------------------------

const COLOURS: Record<GraphNode['type'], string> = {
  organisation: '#1B2A4A', // navy
  idea: '#2D8B7A',         // teal (Good Ship brand accent)
  strategy: '#D4993D',     // amber (Good Ship secondary accent)
};

// Cluster colour palette — cycled per cluster_id so the frontend can
// colour-code nodes by cluster membership when the "Clusters" toggle is on.
const CLUSTER_COLOURS = ['#2D8B7A', '#D4993D', '#C75B3A', '#8BA4B8', '#1B2A4A', '#243556'];

function clusterColour(clusterId: number): string {
  return CLUSTER_COLOURS[(clusterId - 1) % CLUSTER_COLOURS.length];
}

const INCOME_BAND_ORDER = [
  'under_10k', '10k-100k', '100k-250k', '250k-500k',
  '500k-1m', '1m-5m', '5m-10m', '10m-100m', 'over_100m',
];

function incomeBandRank(band: string | null | undefined): number {
  if (!band) return 0;
  const idx = INCOME_BAND_ORDER.indexOf(band);
  return idx === -1 ? 0 : idx;
}

function costRank(cost: [number, number] | null | undefined): number {
  if (!cost) return 0;
  const avg = (cost[0] + cost[1]) / 2;
  // Map 0..500k to 0..8 roughly (log-ish). 50k -> ~3, 250k -> ~6.
  if (avg <= 0) return 0;
  return Math.min(8, Math.max(0, Math.round(Math.log10(avg / 5_000) * 2)));
}

function nodeRadius(node: GraphNode): number {
  switch (node.type) {
    case 'organisation':
      return 8 + incomeBandRank(node.income_band) * 2;
    case 'idea':
      return 8 + costRank(node.cost_range) * 2;
    case 'strategy':
      return 12; // fixed medium
  }
}

// --- internal simulation types --------------------------------------------

interface SimNode extends d3.SimulationNodeDatum, GraphNode {}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: GraphEdge['type'];
  weight?: number | null;
  relationship?: string;
  description?: string;
}

type EdgeStyle = { stroke: string; width: number; dash: string; directed: boolean; derived: boolean };

const EDGE_STROKE: Record<GraphEdge['type'], EdgeStyle> = {
  org_idea: { stroke: '#888', width: 1.5, dash: 'none', directed: false, derived: false },
  org_strategy: { stroke: '#888', width: 1.5, dash: 'none', directed: false, derived: false },
  shared_theme: { stroke: '#2D8B7A', width: 2.5, dash: '6 4', directed: false, derived: true },
  shared_area: { stroke: '#aaa', width: 1, dash: '2 4', directed: false, derived: true },
  strategy_idea: { stroke: '#2D8B7A', width: 2, dash: 'none', directed: true, derived: false },
  idea_idea_shared_theme: { stroke: '#2D8B7A', width: 1.5, dash: '6 4', directed: false, derived: true },
  idea_idea_shared_place: { stroke: '#8BA4B8', width: 1, dash: '2 4', directed: false, derived: true },
  idea_idea_explicit: { stroke: '#D4993D', width: 2, dash: 'none', directed: false, derived: false },
  strategy_strategy_shared_theme: { stroke: '#1B2A4A', width: 1.5, dash: '6 4', directed: false, derived: true },
  idea_org_connection: { stroke: '#C75B3A', width: 1.5, dash: 'none', directed: true, derived: false },
};

const EDGE_LEGEND: Array<{ type: GraphEdge['type']; label: string }> = [
  { type: 'org_idea', label: 'Org owns idea' },
  { type: 'org_strategy', label: 'Org owns strategy' },
  { type: 'shared_theme', label: 'Shared theme (org↔org)' },
  { type: 'shared_area', label: 'Shared area (org↔org)' },
  { type: 'strategy_idea', label: 'Strategy → idea' },
  { type: 'idea_idea_shared_theme', label: 'Idea ↔ idea (shared theme)' },
  { type: 'idea_idea_shared_place', label: 'Idea ↔ idea (shared place)' },
  { type: 'idea_idea_explicit', label: 'Idea ↔ idea (explicit)' },
  { type: 'strategy_strategy_shared_theme', label: 'Strategy ↔ strategy (shared theme)' },
  { type: 'idea_org_connection', label: 'Idea → org (explicit connection)' },
];

// --- component -------------------------------------------------------------

const WIDTH = 800;
const HEIGHT = 600;

export default function GraphDiscovery() {
  const [selectedThemes, setSelectedThemes] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hoveredEdgeIndex, setHoveredEdgeIndex] = useState<number | null>(null);
  const [explicitOnly, setExplicitOnly] = useState(false);
  const [colourByCluster, setColourByCluster] = useState(false);
  const [highlightedClusterIdx, setHighlightedClusterIdx] = useState<number | null>(null);

  const themesQuery = useThemes();
  const themes: ThemeEntry[] = themesQuery.data ?? [];

  const themeList = useMemo(
    () => Array.from(selectedThemes).sort(),
    [selectedThemes],
  );
  const graphQuery = useGraphData(themeList, 200);
  const graphData: GraphData | undefined = graphQuery.data;

  const svgRef = useRef<SVGSVGElement | null>(null);
  // Build simulation nodes/links from the fetched data.
  const { simNodes, simLinks } = useMemo(() => {
    if (!graphData) return { simNodes: [] as SimNode[], simLinks: [] as SimLink[] };
    const nodeById = new Map<string, SimNode>();
    // Seed initial positions in a circle so nodes render even before the
    // force simulation ticks (important for jsdom/happy-dom test envs where
    // requestAnimationFrame isn't available).
    const count = graphData.nodes.length;
    const nodes: SimNode[] = graphData.nodes.map((n, i) => {
      const angle = (i / Math.max(count, 1)) * 2 * Math.PI;
      return {
        ...n,
        x: WIDTH / 2 + Math.cos(angle) * 150,
        y: HEIGHT / 2 + Math.sin(angle) * 150,
      };
    });
    nodes.forEach((n) => nodeById.set(n.id, n));
    const links: SimLink[] = graphData.edges
      .map((e) => {
        const source = nodeById.get(e.source);
        const target = nodeById.get(e.target);
        if (!source || !target) return null;
        return {
          source,
          target,
          type: e.type,
          weight: e.weight ?? undefined,
          relationship: e.relationship,
          description: e.description,
        } as SimLink;
      })
      .filter((l): l is SimLink => l !== null);
    return { simNodes: nodes, simLinks: links };
  }, [graphData]);

  // D3 force simulation — runs in an effect, writes positions back to state
  // on each tick so React re-renders the SVG.
  const [, forceTick] = useState(0);
  const simulationRef = useRef<d3.Simulation<SimNode, undefined> | null>(null);

  useEffect(() => {
    if (simNodes.length === 0) {
      simulationRef.current?.stop();
      simulationRef.current = null;
      return;
    }

    const sim = d3
      .forceSimulation<SimNode>(simNodes)
      // Higher velocity decay damps the layout so it glides to rest instead of
      // jittering; a gentle alpha decay lets it settle gracefully on load.
      .velocityDecay(0.45)
      .alphaDecay(0.035)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance((l) =>
            l.type === 'shared_theme' || l.type === 'shared_area' ? 120 : 60,
          )
          .strength(0.3),
      )
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .force(
        'collide',
        d3.forceCollide<SimNode>().radius((d) => nodeRadius(d) + 4),
      )
      .on('tick', () => forceTick((t) => t + 1));

    simulationRef.current = sim;
    return () => {
      sim.stop();
    };
    // simNodes/simLinks are recreated when graphData changes; the effect deps
    // capture identity so we rebuild the simulation each time.
  }, [simNodes, simLinks, forceTick]);

  // --- zoom + pan ----------------------------------------------------------
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);
  const transformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  transformRef.current = transform;
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 4])
      // Don't start a pan when the gesture begins on a node — node drag owns
      // that interaction. Wheel-zoom and background drags still pan.
      .filter((event: Event) => {
        const target = event.target as Element | null;
        if (target?.closest?.('[data-node]')) return false;
        const e = event as MouseEvent;
        return (!e.ctrlKey || event.type === 'wheel') && !e.button;
      })
      .on('zoom', (event) => setTransform(event.transform));
    zoomRef.current = zoom;
    d3.select(svg).call(zoom);
    return () => {
      d3.select(svg).on('.zoom', null);
    };
  }, []);

  // --- zoom controls (buttons) --------------------------------------------
  function zoomBy(factor: number) {
    const svg = svgRef.current;
    if (!svg || !zoomRef.current) return;
    d3.select(svg).transition().duration(200).call(zoomRef.current.scaleBy, factor);
  }
  function resetZoom() {
    const svg = svgRef.current;
    if (!svg || !zoomRef.current) return;
    d3.select(svg)
      .transition()
      .duration(300)
      .call(zoomRef.current.transform, d3.zoomIdentity);
  }
  function fitToView() {
    const svg = svgRef.current;
    if (!svg || !zoomRef.current || simNodes.length === 0) return;
    const xs = simNodes.map((n) => n.x ?? WIDTH / 2);
    const ys = simNodes.map((n) => n.y ?? HEIGHT / 2);
    const pad = 40;
    const minX = Math.min(...xs) - pad;
    const maxX = Math.max(...xs) + pad;
    const minY = Math.min(...ys) - pad;
    const maxY = Math.max(...ys) + pad;
    const w = Math.max(maxX - minX, 1);
    const h = Math.max(maxY - minY, 1);
    const scale = Math.min(4, Math.max(0.25, Math.min(WIDTH / w, HEIGHT / h)));
    const tx = WIDTH / 2 - scale * (minX + maxX) / 2;
    const ty = HEIGHT / 2 - scale * (minY + maxY) / 2;
    d3.select(svg)
      .transition()
      .duration(400)
      .call(
        zoomRef.current.transform,
        d3.zoomIdentity.translate(tx, ty).scale(scale),
      );
  }

  // --- node dragging -------------------------------------------------------
  // Pointer-based drag that pins a node where it's dropped (fx/fy). Double-
  // click releases the pin back to the simulation. We convert pointer client
  // coords into graph space by inverting the current zoom transform.
  const dragRef = useRef<{ id: string; moved: boolean } | null>(null);

  function clientToGraph(clientX: number, clientY: number): [number, number] {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const rect = svg.getBoundingClientRect();
    const scaleX = rect.width ? WIDTH / rect.width : 1;
    const scaleY = rect.height ? HEIGHT / rect.height : 1;
    const px = (clientX - rect.left) * scaleX;
    const py = (clientY - rect.top) * scaleY;
    return transformRef.current.invert([px, py]) as [number, number];
  }

  function onNodePointerDown(node: SimNode, e: ReactPointerEvent<Element>) {
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    dragRef.current = { id: node.id, moved: false };
    simulationRef.current?.alphaTarget(0.3).restart();
    node.fx = node.x;
    node.fy = node.y;
  }
  function onNodePointerMove(node: SimNode, e: ReactPointerEvent<Element>) {
    if (dragRef.current?.id !== node.id) return;
    dragRef.current.moved = true;
    const [gx, gy] = clientToGraph(e.clientX, e.clientY);
    node.fx = gx;
    node.fy = gy;
    forceTick((t) => t + 1);
  }
  function onNodePointerUp(node: SimNode, e: ReactPointerEvent<Element>) {
    if (dragRef.current?.id !== node.id) return;
    (e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
    simulationRef.current?.alphaTarget(0);
    // fx/fy left set → node stays pinned where it was dropped.
  }
  function releasePin(node: SimNode) {
    node.fx = null;
    node.fy = null;
    simulationRef.current?.alphaTarget(0.3).restart();
    window.setTimeout(() => simulationRef.current?.alphaTarget(0), 600);
  }

  // --- hover neighbourhood -------------------------------------------------
  const connectedIds = useMemo(() => {
    const focus = hoveredId ?? selectedNode?.id ?? null;
    if (!focus) return null;
    const ids = new Set<string>([focus]);
    for (const link of simLinks) {
      const s = (link.source as SimNode).id ?? (link.source as unknown as string);
      const t = (link.target as SimNode).id ?? (link.target as unknown as string);
      if (s === focus) ids.add(t);
      if (t === focus) ids.add(s);
    }
    return ids;
  }, [hoveredId, selectedNode, simLinks]);

  // --- cluster highlight (card click) --------------------------------------
  // When a cluster card is clicked, only nodes in that cluster (by index in
  // summary.clusters order) stay bright; everything else dims. Mapping from
  // cluster index → set of node ids uses the cluster_id stamps on the nodes.
  const highlightedClusterIds = useMemo(() => {
    if (highlightedClusterIdx === null || !graphData) return null;
    const clusters = graphData.graph_summary?.clusters ?? [];
    const target = clusters[highlightedClusterIdx];
    if (!target) return null;
    // Cluster index in summary order is 0-based; node.cluster_id is the 1-based
    // backend id. Sort clusters by node_count desc to mirror the backend's
    // ordering, then map by position. Since the backend sorts clusters by
    // size, the summary array order already aligns with cluster_id order
    // (largest cluster has cluster_id 1).
    const clusterId = highlightedClusterIdx + 1;
    const ids = new Set<string>();
    for (const n of graphData.nodes) {
      if (n.cluster_id === clusterId) ids.add(n.id);
    }
    return ids;
  }, [highlightedClusterIdx, graphData]);

  function isDimmed(id: string): boolean {
    if (highlightedClusterIds !== null) {
      return !highlightedClusterIds.has(id);
    }
    return connectedIds !== null && !connectedIds.has(id);
  }

  function isEdgeDimmed(sourceId: string, targetId: string): boolean {
    if (highlightedClusterIds !== null) {
      return !(highlightedClusterIds.has(sourceId) && highlightedClusterIds.has(targetId));
    }
    if (!connectedIds) return false;
    return !(connectedIds.has(sourceId) && connectedIds.has(targetId));
  }

  // --- theme filter --------------------------------------------------------
  function toggleTheme(key: string) {
    setSelectedThemes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // --- edge label ----------------------------------------------------------
  function edgeLabel(link: SimLink): string | null {
    if (link.relationship) return link.relationship;
    if (link.description) return link.description;
    if (link.weight && link.weight > 1) return `${link.weight} shared`;
    return null;
  }

  // --- visible links (explicit-only filter) --------------------------------
  const visibleLinks = useMemo(() => {
    if (!explicitOnly) return simLinks;
    // Unknown edge types (newer backend than bundle) can't be classified as
    // explicit, so hide them in explicit-only mode rather than crashing.
    return simLinks.filter((l) => {
      const style = EDGE_STROKE[l.type];
      return style ? !style.derived : false;
    });
  }, [simLinks, explicitOnly]);

  // --- detail link ---------------------------------------------------------
  function detailUrl(node: SimNode): string {
    if (node.type === 'organisation') return `/openorg/${node.id}`;
    if (node.org_id) {
      const slug = node.id.split(':').slice(2).join(':');
      if (node.type === 'idea') return `/openorg/${node.org_id}/ideas/${slug}`;
      if (node.type === 'strategy') return `/openorg/${node.org_id}/strategies/${slug}`;
    }
    return '#';
  }

  const summary = graphData?.graph_summary;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      {/* --- left: graph + filters ------------------------------------- */}
      <div>
        {/* graph summary */}
        {summary && (
          <p className="mb-3 text-sm text-grey-blue">
            {summary.organisations} organisation{summary.organisations === 1 ? '' : 's'},{' '}
            {summary.ideas} idea{summary.ideas === 1 ? '' : 's'},{' '}
            {summary.strategies} strateg{summary.strategies === 1 ? 'y' : 'ies'}.{' '}
            {summary.clusters.length} cluster{summary.clusters.length === 1 ? '' : 's'} detected.
          </p>
        )}

        {/* theme filter checkboxes + explicit-only toggle */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {themes.length > 0 && (
            <fieldset className="border border-rule bg-cream-dark p-3">
              <legend className="kicker px-1">Filter by theme</legend>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
                {themes.map((t) => (
                  <label
                    key={t.key}
                    className="flex items-center gap-1.5 text-sm text-navy"
                  >
                    <input
                      type="checkbox"
                      checked={selectedThemes.has(t.key)}
                      onChange={() => toggleTheme(t.key)}
                      aria-label={t.label}
                    />
                    <span>{t.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <button
            type="button"
            aria-pressed={explicitOnly}
            onClick={() => setExplicitOnly((v) => !v)}
            className={
              'px-3 py-1.5 text-sm transition ' +
              (explicitOnly
                ? 'bg-navy text-cream'
                : 'border border-rule text-navy hover:bg-cream-dark')
            }
          >
            Show only explicit connections
          </button>
          <button
            type="button"
            aria-pressed={colourByCluster}
            onClick={() => setColourByCluster((v) => !v)}
            className={
              'px-3 py-1.5 text-sm transition ' +
              (colourByCluster
                ? 'bg-navy text-cream'
                : 'border border-rule text-navy hover:bg-cream-dark')
            }
          >
            Clusters
          </button>
        </div>

        {/* --- cluster summary panel ----------------------------------- */}
        {graphData?.graph_summary && (
          <div className="mb-4 border border-rule bg-cream-dark p-3">
            <div className="kicker mb-2">Landscape</div>
            <p className="text-sm text-navy" data-testid="landscape-counts">
              {graphData.graph_summary.organisations} organisation{graphData.graph_summary.organisations !== 1 ? 's' : ''},{' '}
              {graphData.graph_summary.ideas} idea{graphData.graph_summary.ideas !== 1 ? 's' : ''},{' '}
              {graphData.graph_summary.strategies} strateg{graphData.graph_summary.strategies !== 1 ? 'ies' : 'y'}.
            </p>
            {graphData.graph_summary.clusters.length > 0 ? (
              <div className="mt-2 space-y-2">
                {graphData.graph_summary.clusters.map((cluster, idx) => (
                  <button
                    key={idx}
                    data-testid="cluster-card"
                    type="button"
                    onClick={() =>
                      setHighlightedClusterIdx(
                        highlightedClusterIdx === idx ? null : idx,
                      )
                    }
                    className="block w-full border border-rule bg-cream p-3 text-left transition hover:border-navy"
                  >
                    <p className="text-sm text-navy">{cluster.description}</p>
                    {(cluster.places?.length ?? 0) > 0 && (
                      <p className="mt-1 text-xs text-grey-blue">
                        Places: {(cluster.places ?? []).join(', ')}
                      </p>
                    )}
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {cluster.dominant_themes?.map((t) => (
                        <span
                          key={t}
                          data-cluster-theme-chip
                          className="border border-teal/40 bg-teal/10 px-1.5 py-0.5 text-xs text-teal"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-grey-blue">No clusters — all organisations are isolated.</p>
            )}
          </div>
        )}

        {!graphQuery.isLoading && !graphQuery.isError && simNodes.length > 0 && (
          <p className="mb-2 text-xs text-grey-blue">
            Drag nodes to rearrange · double-click to release · scroll to zoom ·
            click a node to focus its connections.
          </p>
        )}

        {graphQuery.isLoading ? (
          <div className="flex h-[600px] items-center justify-center border border-rule text-grey-blue">
            Loading graph…
          </div>
        ) : graphQuery.isError ? (
          <div className="flex h-[600px] items-center justify-center border border-rule text-red-700">
            Couldn't load the graph.
          </div>
        ) : simNodes.length === 0 ? (
          <div className="flex h-[600px] items-center justify-center border border-rule text-grey-blue">
            No data to visualise.
          </div>
        ) : (
          <div className="relative">
            {/* zoom + view controls */}
            <div
              data-testid="graph-controls"
              className="absolute right-3 top-3 z-10 flex flex-col overflow-hidden rounded-brand border border-rule bg-cream/90 shadow-sm backdrop-blur"
            >
              <button
                type="button"
                aria-label="Zoom in"
                onClick={() => zoomBy(1.3)}
                className="px-2.5 py-1.5 text-navy transition hover:bg-cream-dark"
              >
                +
              </button>
              <button
                type="button"
                aria-label="Zoom out"
                onClick={() => zoomBy(1 / 1.3)}
                className="border-t border-rule px-2.5 py-1.5 text-navy transition hover:bg-cream-dark"
              >
                −
              </button>
              <button
                type="button"
                aria-label="Fit to view"
                onClick={fitToView}
                className="border-t border-rule px-2.5 py-1.5 text-xs text-navy transition hover:bg-cream-dark"
              >
                Fit
              </button>
              <button
                type="button"
                aria-label="Reset view"
                onClick={resetZoom}
                className="border-t border-rule px-2.5 py-1.5 text-xs text-navy transition hover:bg-cream-dark"
              >
                Reset
              </button>
            </div>
          <svg
            ref={svgRef}
            width={WIDTH}
            height={HEIGHT}
            className="block w-full border border-rule"
            style={{ cursor: 'grab', touchAction: 'none' }}
            onClick={() => {
              setSelectedNode(null);
              setHighlightedClusterIdx(null);
            }}
          >
            <defs>
              <marker
                id="arrowhead"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#7C8DA0" />
              </marker>
              <radialGradient id="graphBg" cx="50%" cy="42%" r="75%">
                <stop offset="0%" stopColor="#FBF7EE" />
                <stop offset="100%" stopColor="#F0E9DA" />
              </radialGradient>
              <filter id="nodeShadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow
                  dx="0"
                  dy="1"
                  stdDeviation="1.5"
                  floodColor="#1B2A4A"
                  floodOpacity="0.18"
                />
              </filter>
            </defs>
            <rect width={WIDTH} height={HEIGHT} fill="url(#graphBg)" />
            <g transform={transform.toString()}>
              {/* edges */}
              {visibleLinks.map((link, i) => {
                const s = link.source as SimNode;
                const t = link.target as SimNode;
                if (s.x == null || s.y == null || t.x == null || t.y == null) return null;
                const style = EDGE_STROKE[link.type];
                // Forward-compat: the backend may ship a new semantic edge type
                // before this bundle knows about it. Skip unknown types instead
                // of crashing on style.stroke (see fix/openorg-hardening).
                if (!style) return null;
                const dim = isEdgeDimmed(s.id, t.id);
                return (
                  <line
                    key={`edge-${i}`}
                    data-edge-type={link.type}
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={style.stroke}
                    strokeWidth={style.width}
                    strokeDasharray={style.dash === 'none' ? undefined : style.dash}
                    opacity={dim ? 0.15 : 0.7}
                    markerEnd={style.directed ? 'url(#arrowhead)' : undefined}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredEdgeIndex(i)}
                    onMouseLeave={() => setHoveredEdgeIndex(null)}
                  />
                );
              })}

              {/* edge hover label */}
              {hoveredEdgeIndex != null && visibleLinks[hoveredEdgeIndex] && (() => {
                const link = visibleLinks[hoveredEdgeIndex];
                const s = link.source as SimNode;
                const t = link.target as SimNode;
                if (s.x == null || s.y == null || t.x == null || t.y == null) return null;
                const mx = (s.x + t.x) / 2;
                const my = (s.y + t.y) / 2;
                const label = edgeLabel(link);
                if (!label) return null;
                return (
                  <text
                    data-edge-label
                    x={mx}
                    y={my - 4}
                    fontSize={10}
                    fill="#1B2A4A"
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                    textAnchor="middle"
                  >
                    {label}
                  </text>
                );
              })()}

              {/* nodes */}
              {simNodes.map((node) => {
                if (node.x == null || node.y == null) return null;
                const r = nodeRadius(node);
                const dim = isDimmed(node.id);
                const focused =
                  hoveredId === node.id || selectedNode?.id === node.id;
                const pinned = node.fx != null && node.fy != null;
                return (
                  <g
                    key={node.id}
                    data-node={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    style={{ cursor: 'grab' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Suppress the click that ends a drag gesture.
                      if (dragRef.current?.moved) {
                        dragRef.current = null;
                        return;
                      }
                      setSelectedNode(node);
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      releasePin(node);
                    }}
                    onPointerDown={(e) => onNodePointerDown(node, e)}
                    onPointerMove={(e) => onNodePointerMove(node, e)}
                    onPointerUp={(e) => onNodePointerUp(node, e)}
                    onMouseEnter={() => setHoveredId(node.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    {/* pinned indicator — a faint dashed ring */}
                    {pinned && (
                      <circle
                        r={r + 4}
                        fill="none"
                        stroke="#2D8B7A"
                        strokeWidth={1}
                        strokeDasharray="2 3"
                        opacity={dim ? 0.2 : 0.7}
                      />
                    )}
                    <circle
                      data-id={node.id}
                      r={r}
                      fill={
                        colourByCluster && node.cluster_id
                          ? clusterColour(node.cluster_id)
                          : COLOURS[node.type]
                      }
                      stroke={focused ? '#2D8B7A' : '#fff'}
                      strokeWidth={focused ? 3 : 1.5}
                      opacity={dim ? 0.25 : 1}
                      filter="url(#nodeShadow)"
                      style={{ transition: 'opacity 200ms ease, stroke 150ms ease' }}
                    />
                    <text
                      x={r + 5}
                      y={4}
                      fontSize={11}
                      fontWeight={focused ? 600 : 400}
                      fill="#1B2A4A"
                      opacity={dim ? 0.3 : 0.92}
                      style={{
                        pointerEvents: 'none',
                        userSelect: 'none',
                        transition: 'opacity 200ms ease',
                      }}
                    >
                      {node.name}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
          </div>
        )}

        {/* legend */}
        <div
          data-testid="graph-legend"
          className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-grey-blue"
        >
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: COLOURS.organisation }} />
            Organisation
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: COLOURS.idea }} />
            Idea
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: COLOURS.strategy }} />
            Strategy
          </span>
          {EDGE_LEGEND.map((e) => {
            const style = EDGE_STROKE[e.type];
            return (
              <span key={e.type} className="flex items-center gap-1.5">
                <svg width="20" height="6" aria-hidden>
                  <line
                    x1="0"
                    y1="3"
                    x2="20"
                    y2="3"
                    stroke={style.stroke}
                    strokeWidth={style.width}
                    strokeDasharray={style.dash === 'none' ? undefined : style.dash}
                  />
                </svg>
                {e.label}
              </span>
            );
          })}
        </div>
      </div>

      {/* --- right: side panel ---------------------------------------- */}
      <aside className="border border-rule bg-cream-dark p-4">
        {selectedNode ? (
          <div>
            <div className="kicker mb-1">{selectedNode.type}</div>
            <h3 className="display-head text-xl font-medium text-navy">
              {selectedNode.name}
            </h3>
            {selectedNode.summary && (
              <p className="mt-2 text-sm text-navy/90">{selectedNode.summary}</p>
            )}
            {selectedNode.themes.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-xs text-grey-blue">
                {selectedNode.themes.map((t) => (
                  <li key={t} className="font-mono">#{t}</li>
                ))}
              </ul>
            )}
            {selectedNode.type === 'organisation' && (
              <dl className="mt-3 space-y-1 text-sm">
                {selectedNode.area && (
                  <div><dt className="inline text-grey-blue">Area: </dt><dd className="inline text-navy">{selectedNode.area}</dd></div>
                )}
                {selectedNode.income_band && (
                  <div><dt className="inline text-grey-blue">Income band: </dt><dd className="inline text-navy">{selectedNode.income_band}</dd></div>
                )}
                {selectedNode.ideas_count != null && (
                  <div><dt className="inline text-grey-blue">Ideas: </dt><dd className="inline text-navy">{selectedNode.ideas_count}</dd></div>
                )}
              </dl>
            )}
            {selectedNode.type === 'idea' && (
              <dl className="mt-3 space-y-1 text-sm">
                {selectedNode.place && (
                  <div><dt className="inline text-grey-blue">Place: </dt><dd className="inline text-navy">{selectedNode.place}</dd></div>
                )}
                {selectedNode.cost_range && (
                  <div>
                    <dt className="inline text-grey-blue">Cost: </dt>
                    <dd className="inline text-navy">
                      £{selectedNode.cost_range[0].toLocaleString()}–£{selectedNode.cost_range[1].toLocaleString()}
                    </dd>
                  </div>
                )}
                {selectedNode.connections && selectedNode.connections.length > 0 && (
                  <div>
                    <dt className="text-grey-blue">Connections:</dt>
                    <dd>
                      <ul className="mt-1 space-y-0.5">
                        {selectedNode.connections.map((c, idx) => (
                          <li key={idx} className="text-navy">
                            {c.org_name}
                            {c.relationship ? <span className="text-grey-blue"> · {c.relationship}</span> : null}
                          </li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                )}
              </dl>
            )}
            {selectedNode.type === 'strategy' && (
              <dl className="mt-3 space-y-1 text-sm">
                {selectedNode.period && (
                  <div>
                    <dt className="inline text-grey-blue">Period: </dt>
                    <dd className="inline text-navy">
                      {selectedNode.period.start ?? '?'}–{selectedNode.period.end ?? '?'}
                    </dd>
                  </div>
                )}
                {selectedNode.priorities_count != null && (
                  <div>
                    <dt className="inline text-grey-blue">Priorities: </dt>
                    <dd className="inline text-navy">{selectedNode.priorities_count} priorities</dd>
                  </div>
                )}
              </dl>
            )}
            {selectedNode.type === 'organisation' ? (
              <Link
                to={detailUrl(selectedNode)}
                className="mt-4 inline-block text-sm text-teal underline"
              >
                View profile →
              </Link>
            ) : selectedNode.type === 'idea' && selectedNode.org_id ? (
              <Link
                to={detailUrl(selectedNode)}
                className="mt-4 inline-block text-sm text-teal underline"
              >
                View idea →
              </Link>
            ) : selectedNode.type === 'strategy' && selectedNode.org_id ? (
              <Link
                to={detailUrl(selectedNode)}
                className="mt-4 inline-block text-sm text-teal underline"
              >
                View strategy →
              </Link>
            ) : selectedNode.org_id ? (
              <Link
                to={`/openorg/${selectedNode.org_id}`}
                className="mt-4 inline-block text-sm text-teal underline"
              >
                View organisation →
              </Link>
            ) : null}
            <button
              type="button"
              className="mt-4 block text-xs text-grey-blue underline-offset-4 hover:text-navy hover:underline"
              onClick={() => setSelectedNode(null)}
            >
              Close panel
            </button>
          </div>
        ) : (
          <p className="text-sm text-grey-blue">
            Click a node to see details.
          </p>
        )}
      </aside>
    </div>
  );
}