# Semantic Graph Connections — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add semantic connections between ideas, strategies, and organisations to the Open Org graph visualisation, enabling funders to see clusters of related intent across organisations — the "landscape of ideas" vision from the essay.

**Context:** The essay "The Grant Application Is Dead" argues that ideas should be first-class objects — visible, connectable, persistent. Funders should browse landscapes of ideas, not applications. They should see clusters forming (e.g., "six organisations across two places all circling similar work"). The existing schemas already support connections — the idea schema has `connections` (complementary/competing/collaborating/referring), `collaborators`, and `linked_strategy_id` fields. The graph API currently only surfaces org→idea, org→strategy, org→org shared_theme, and org→org shared_area edges. We need to add the full semantic connection layer.

**Architecture:** Python FastAPI backend (graph endpoint in `open_org_discovery.py`), React + D3-force frontend (GraphDiscovery component). No new DB tables needed — all connections are derived from existing JSON fields or computed from shared attributes.

---

## Edge types to add

| Edge type | Source | Target | Derivation | Visual |
|-----------|--------|--------|------------|--------|
| `strategy_idea` | strategy node | idea node | `idea.linked_strategy_id` field in the idea JSON | solid directed |
| `idea_idea_shared_theme` | idea node | idea node | Jaccard similarity of themes ≥ 0.3 (at least 1 shared theme) | dashed, weight = shared count |
| `idea_idea_shared_place` | idea node | idea node | Same `place.area_codes` or `place.description` | dotted, weight 1 |
| `idea_idea_explicit` | idea node | idea/org node | `connections[]` array in idea JSON — `org_id` present and matches a published org's idea | solid, labelled with relationship type |
| `strategy_strategy_shared_theme` | strategy node | strategy node | Shared themes between two strategies | dashed, weight = shared count |
| `idea_org_connection` | idea node | org node | `connections[]` array in idea JSON with `org_id` matching a published org | solid, labelled with relationship (complementary/competing/collaborating/referring) |

## Task 1: Extend graph API with semantic edges

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py`
- Test: `packages/api/tests/test_open_org_graph_route.py`

**Changes:**

1. Add new edge types to `GraphEdge.type` — extend the type field to include: `strategy_idea`, `idea_idea_shared_theme`, `idea_idea_shared_place`, `idea_idea_explicit`, `strategy_strategy_shared_theme`, `idea_org_connection`

2. In `_build_graph`, after building org/idea/strategy nodes and existing edges, add:

   a. **Strategy→Idea edges**: For each idea, check `idea_json.get("linked_strategy_id")`. If it matches a strategy's `id` field in the JSON, add an edge from the strategy node to the idea node.

   b. **Idea→Idea shared theme edges**: For each pair of ideas (from different orgs), compute shared themes. If they share at least 1 theme, add an edge with weight = shared count.

   c. **Idea→Idea shared place edges**: For each pair of ideas (from different orgs), compare `place.description` (case-insensitive) or `place.area_codes` overlap. If they match, add an edge.

   d. **Idea→Org explicit connection edges**: For each idea, read `connections[]` from the idea JSON. For each connection with an `org_id` that matches a published org in the graph, add an edge labelled with the `relationship` type.

   e. **Idea→Idea explicit connection edges**: If a connection's `org_id` matches another org that has ideas, and the `relationship` is `complementary` or `collaborating`, add an edge between the ideas (not just org-to-org — the idea-level connection shows intent alignment).

   f. **Strategy→Strategy shared theme edges**: For each pair of strategies (from different orgs), compute shared themes. If they share at least 1 theme, add an edge.

3. Add `relationship` field to `GraphEdge` (optional, for explicit connection edges).

4. Add `description` field to `GraphEdge` (optional, for place-based connections — e.g., "Both in Great Yarmouth").

5. Add `summary` field to `GraphNode` (for ideas and strategies — so the graph can show a snippet in the side panel).

**TDD tests:**
- Strategy with linked idea shows strategy_idea edge
- Two ideas with shared theme show idea_idea_shared_theme edge
- Two ideas in same place show idea_idea_shared_place edge
- Idea with explicit connection to another org shows idea_org_connection edge with relationship label
- Two strategies with shared themes show strategy_strategy_shared_theme edge
- Edge weights are correct for shared theme counts
- Theme filter still works with new edge types
- Limit parameter still works (only limits org nodes; ideas/strategies from filtered orgs are included)

---

## Task 2: Update GraphDiscovery component for new edge types

**Files:**
- Modify: `packages/web/src/components/openorg/GraphDiscovery.tsx`
- Modify: `packages/web/src/components/openorg/GraphDiscovery.test.tsx`
- Modify: `packages/web/src/api/openorg.ts` (update GraphEdge interface)

**Changes:**

1. Update `GraphEdge` TypeScript interface to include new edge types and optional `relationship`/`description` fields.

2. Update `EDGE_STROKE` constant to include new edge types with distinct visual styling:
   - `strategy_idea`: solid teal, width 2 (directed — shows the strategy→idea link)
   - `idea_idea_shared_theme`: dashed teal, width 1.5, opacity 0.5
   - `idea_idea_shared_place`: dotted grey-blue, width 1, opacity 0.4
   - `idea_idea_explicit`: solid amber, width 2 (explicit connection — visually emphasised)
   - `strategy_strategy_shared_theme`: dashed navy, width 1.5, opacity 0.4
   - `idea_org_connection`: solid coral, width 1.5 (cross-org connection — different from ownership)

3. Render directed edges with arrowheads for `strategy_idea` and `idea_org_connection` (these are directional — a strategy links to an idea, an idea references an org).

4. Show edge labels on hover — when hovering over an edge (or when a connected node is selected), display the relationship type or place description.

5. Update the side panel to show:
   - For idea nodes: summary, themes, place, cost range, connections list (org names + relationship)
   - For strategy nodes: summary, themes, period, priorities count
   - Links to detail pages for ideas and strategies (not just orgs)

6. Update the legend to show all edge types.

7. Update node sizing: ideas with more connections get slightly larger (network centrality signal — an idea that connects to many others is a "hub" idea).

8. Add a filter toggle: "Show only explicit connections" — when on, hides derived (shared_theme/shared_place) edges and shows only explicit connections (strategy_idea, idea_org_connection, idea_idea_explicit). This lets funders see what organisations have deliberately linked vs what's semantically inferred.

**Tests:**
- New edge types render with correct stroke styles
- Strategy→idea edge renders with arrowhead
- Edge labels appear on hover
- Side panel shows idea summary when idea node clicked
- Filter toggle hides/shows derived edges

---

## Task 3: Add "connection strength" summary to graph response

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py`

Add a `summary` field to `GraphPayload` with aggregate stats:
- `total_nodes`, `total_edges`
- `by_type`: counts per node type and edge type
- `clusters`: list of connected component descriptions (groups of nodes that form a cluster — e.g., "3 organisations, 5 ideas around food_access in Great Yarmouth")

This gives funders a quick read on the landscape without having to visually parse the graph.

---

## Task 4: Update Discover page with graph legend + cluster summary

**Files:**
- Modify: `packages/web/src/pages/openorg/Discover.tsx`

Show the cluster summary above the graph when in graph mode — "X organisations, Y ideas, Z strategies. N clusters detected."

---

## Task 5: Commit, verify, push

Run all tests, tsc, lint. Commit on `fix/openorg-hardening`. Push.