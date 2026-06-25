/**
 * GraphDiscovery — force-directed graph visualisation for Open Org discovery.
 *
 * Uses d3-force for layout and renders SVG via React. Nodes are coloured by
 * type (organisation / idea / strategy), sized by income band or cost range.
 * Edges show ownership, shared themes, and shared areas. Supports hover
 * highlighting, click-to-detail-panel, zoom/pan, and theme filter checkboxes.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import * as d3 from 'd3';
import {
  type GraphData,
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
  type: GraphEdgeType;
  weight?: number | null;
}

type GraphEdgeType = 'org_idea' | 'org_strategy' | 'shared_theme' | 'shared_area';

const EDGE_STROKE: Record<GraphEdgeType, { stroke: string; width: number; dash: string }> = {
  org_idea: { stroke: '#888', width: 1.5, dash: 'none' },
  org_strategy: { stroke: '#888', width: 1.5, dash: 'none' },
  shared_theme: { stroke: '#2D8B7A', width: 2.5, dash: '6 4' },
  shared_area: { stroke: '#aaa', width: 1, dash: '2 4' },
};

// --- component -------------------------------------------------------------

const WIDTH = 800;
const HEIGHT = 600;

export default function GraphDiscovery() {
  const [selectedThemes, setSelectedThemes] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

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
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 4])
      .on('zoom', (event) => setTransform(event.transform));
    zoomRef.current = zoom;
    d3.select(svg).call(zoom);
    return () => {
      d3.select(svg).on('.zoom', null);
    };
  }, []);

  // --- hover neighbourhood -------------------------------------------------
  const connectedIds = useMemo(() => {
    if (!hoveredId) return null;
    const ids = new Set<string>([hoveredId]);
    for (const link of simLinks) {
      const s = (link.source as SimNode).id ?? (link.source as unknown as string);
      const t = (link.target as SimNode).id ?? (link.target as unknown as string);
      if (s === hoveredId) ids.add(t);
      if (t === hoveredId) ids.add(s);
    }
    return ids;
  }, [hoveredId, simLinks]);

  function isDimmed(id: string): boolean {
    return connectedIds !== null && !connectedIds.has(id);
  }

  function isEdgeDimmed(sourceId: string, targetId: string): boolean {
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

  // --- detail link ---------------------------------------------------------
  function detailUrl(node: SimNode): string {
    if (node.type === 'organisation') return `/openorg/${node.id}`;
    if (node.org_id) {
      if (node.type === 'idea') {
        const slug = node.id.split(':').slice(2).join(':');
        return `/openorg/${node.org_id}?idea=${slug}`;
      }
      if (node.type === 'strategy') {
        const slug = node.id.split(':').slice(2).join(':');
        return `/openorg/${node.org_id}?strategy=${slug}`;
      }
    }
    return '#';
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      {/* --- left: graph + filters ------------------------------------- */}
      <div>
        {/* theme filter checkboxes */}
        {themes.length > 0 && (
          <fieldset className="mb-4 border border-rule bg-cream-dark p-3">
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
          <svg
            ref={svgRef}
            width={WIDTH}
            height={HEIGHT}
            className="block border border-rule bg-cream"
            style={{ cursor: 'grab' }}
          >
            <g transform={transform.toString()}>
              {/* edges */}
              {simLinks.map((link, i) => {
                const s = link.source as SimNode;
                const t = link.target as SimNode;
                if (s.x == null || s.y == null || t.x == null || t.y == null) return null;
                const style = EDGE_STROKE[link.type];
                return (
                  <line
                    key={`edge-${i}`}
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={style.stroke}
                    strokeWidth={style.width}
                    strokeDasharray={style.dash === 'none' ? undefined : style.dash}
                    opacity={isEdgeDimmed(s.id, t.id) ? 0.15 : 0.7}
                  />
                );
              })}

              {/* nodes */}
              {simNodes.map((node) => {
                if (node.x == null || node.y == null) return null;
                const r = nodeRadius(node);
                const dim = isDimmed(node.id);
                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    style={{ cursor: 'pointer' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedNode(node);
                    }}
                    onMouseEnter={() => setHoveredId(node.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <circle
                      data-id={node.id}
                      r={r}
                      fill={COLOURS[node.type]}
                      stroke="#fff"
                      strokeWidth={1.5}
                      opacity={dim ? 0.25 : 1}
                    />
                    <text
                      x={r + 4}
                      y={4}
                      fontSize={11}
                      fill="#1B2A4A"
                      opacity={dim ? 0.3 : 1}
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {node.name}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        )}

        {/* legend */}
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-grey-blue">
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
            {selectedNode.type === 'idea' && selectedNode.cost_range && (
              <p className="mt-3 text-sm text-navy">
                Cost: £{selectedNode.cost_range[0].toLocaleString()}–£{selectedNode.cost_range[1].toLocaleString()}
              </p>
            )}
            {selectedNode.type === 'organisation' ? (
              <Link
                to={detailUrl(selectedNode)}
                className="mt-4 inline-block text-sm text-teal underline"
              >
                View profile →
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