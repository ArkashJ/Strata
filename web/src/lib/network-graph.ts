// Pure derivation for the related-entities network graph (PR14). No React, no
// network, no vis-network — given the three list-endpoint payloads plus a root
// concept slug, it returns a deterministic {nodes, edges} neighbourhood that the
// modal renders. Kept side-effect-free so the topology is unit-testable in
// isolation and the renderer never recomputes it.
//
// The graph is concept-rooted. Around a root concept we surface the entities it
// is wired to and the *shared signals* that connect them — the same join keys the
// pyramid (lib/pyramid.ts) and registry use:
//
//   root concept ──measures──▶ primitive            (primitive.concept_slug === root, or root.measurements[])
//   root concept ──applies──▶  framework            (framework.applicable_to includes root)
//   root concept ──same-lens──▶ concept             (other concept shares primary_lens)
//   root concept ──shared-measurement──▶ concept    (other concept measures a primitive the root also measures)
//   framework   ──same-method-family──▶ framework   (frameworks sharing method_family, both reachable from root)
//
// Each edge carries the signal that justifies it (type + human label + the value
// that is shared), which drives the sidebar bullets and the pattern-detection
// pass (3+ edges sharing one signal value → likely cluster). This mirrors the
// network-graph-modal skill's data contract (`signals[]` with type/label/detail)
// while staying in Strata's vocabulary.

import type { ConceptDetail, ConceptSummary, FrameworkSummary, PrimitiveSummary } from "./schemas";

export type NetEntityKind = "concept" | "primitive" | "framework";

// Signal = the shared data point that justifies an edge. `value` participates in
// pattern detection (a value shared by 3+ edges thickens them); a signal with no
// value still renders in the sidebar but sits out pattern detection.
export interface NetSignal {
  type: "primary_lens" | "method_family" | "measures" | "applies_to" | "shared_measurement";
  label: string;
  value?: string;
}

export interface NetNode {
  id: string;
  kind: NetEntityKind;
  slug: string;
  label: string;
  // Depth from the root (root = 0). Multi-hop expansion stamps deeper nodes.
  depth: number;
  // The node id this one was introduced by (root has none). Branch-collapse
  // walks this to remove everything a node brought in.
  addedBy?: string;
  // Sub-kind that drives node colour for primitives (atomic vs composite) — the
  // summary payload only exposes `kind`, so colour keys off that.
  subKind?: string;
}

export interface NetEdge {
  id: string;
  from: string;
  to: string;
  signals: NetSignal[];
}

export interface NetworkGraph {
  nodes: NetNode[];
  edges: NetEdge[];
}

// Node id namespacing keeps a concept slug and a like-named primitive slug from
// colliding in the vis-network DataSet (ids must be globally unique).
export function nodeId(kind: NetEntityKind, slug: string): string {
  return `${kind}:${slug}`;
}

function humanize(raw: string): string {
  return raw
    .split(/[_-]/)
    .filter(Boolean)
    .map((s) => (s[0]?.toUpperCase() ?? "") + s.slice(1))
    .join(" ");
}

// Stable edge id from an unordered node pair, so re-deriving the same connection
// (e.g. concept↔concept from either side) dedupes to one edge.
function edgeKey(a: string, b: string): string {
  return [a, b].sort().join("__");
}

export interface BuildInput {
  rootSlug: string;
  concepts: ConceptSummary[];
  primitives: PrimitiveSummary[];
  frameworks: FrameworkSummary[];
  // Optional hydrated root record — when present, root.measurements[] is folded
  // in so primitives that measure the concept but carry a different concept_slug
  // (cross-concept measurements) still attach. Absent on first paint.
  rootDetail?: Pick<ConceptDetail, "measurements"> | null;
}

/**
 * Derive the 1-hop neighbourhood around `rootSlug`. Deterministic: every output
 * collection is sorted by slug so the layout is stable and tests can assert on
 * order. Unknown root slug yields a single root node with no edges (the modal
 * surfaces an empty-neighbourhood state rather than throwing).
 */
export function buildNetworkGraph(input: BuildInput): NetworkGraph {
  const { rootSlug, concepts, primitives, frameworks, rootDetail } = input;

  const rootConcept = concepts.find((c) => c.slug === rootSlug);
  const rootId = nodeId("concept", rootSlug);

  const nodes = new Map<string, NetNode>();
  const edges = new Map<string, NetEdge>();

  nodes.set(rootId, {
    id: rootId,
    kind: "concept",
    slug: rootSlug,
    label: rootConcept?.name ?? humanize(rootSlug),
    depth: 0,
  });

  // Nothing else to wire if the root isn't a known concept.
  if (!rootConcept) return finalize(nodes, edges);

  const rootLens = rootConcept.primary_lens;

  const addNode = (node: NetNode) => {
    if (!nodes.has(node.id)) nodes.set(node.id, node);
  };
  const addEdge = (from: string, to: string, signal: NetSignal) => {
    const id = edgeKey(from, to);
    const existing = edges.get(id);
    if (existing) {
      // Merge signals; a concept↔concept pair can share both lens and a
      // measurement, and both should show on the connection.
      if (!existing.signals.some((s) => s.type === signal.type && s.value === signal.value)) {
        existing.signals.push(signal);
      }
      return;
    }
    edges.set(id, { id, from, to, signals: [signal] });
  };

  // ── Primitives that measure the root concept ───────────────────────────────
  // concept_slug match is the primary link; root.measurements[] folds in any
  // primitive explicitly listed on the hydrated root even if its concept_slug
  // differs (a primitive can be reused across concepts).
  const rootMeasurementSlugs = new Set<string>(rootDetail?.measurements ?? []);
  const measuredByRoot = new Set<string>();
  for (const p of primitives) {
    const measures = p.concept_slug === rootSlug || rootMeasurementSlugs.has(p.slug);
    if (!measures) continue;
    measuredByRoot.add(p.slug);
    const pid = nodeId("primitive", p.slug);
    addNode({
      id: pid,
      kind: "primitive",
      slug: p.slug,
      label: p.name,
      depth: 1,
      addedBy: rootId,
      subKind: p.kind,
    });
    addEdge(rootId, pid, {
      type: "measures",
      label: "Measures this concept",
      value: rootSlug,
    });
  }

  // ── Frameworks applicable to the root concept ──────────────────────────────
  // applicable_to lives only on the framework *detail* record, which the list
  // payload omits, so the root→framework edge is materialised during expansion
  // (the modal hydrates frameworks then). Here we still surface the frameworks
  // whose lens matches the root's lens as candidate applications, because the
  // pyramid join treats lens coherence as the applicability proxy at summary
  // granularity.
  const lensFrameworks = frameworks.filter((f) => f.lens === rootLens);
  for (const f of lensFrameworks) {
    const fid = nodeId("framework", f.slug);
    addNode({
      id: fid,
      kind: "framework",
      slug: f.slug,
      label: f.name,
      depth: 1,
      addedBy: rootId,
      subKind: f.method_family,
    });
    addEdge(rootId, fid, {
      type: "applies_to",
      label: "Framework for this lens",
      value: rootLens,
    });
  }

  // Frameworks reachable from the root that share a method family connect to
  // each other (quantitative-axis sibling signal).
  for (let i = 0; i < lensFrameworks.length; i++) {
    for (let j = i + 1; j < lensFrameworks.length; j++) {
      const a = lensFrameworks[i];
      const b = lensFrameworks[j];
      if (a.method_family && a.method_family === b.method_family) {
        addEdge(nodeId("framework", a.slug), nodeId("framework", b.slug), {
          type: "method_family",
          label: "Same method family",
          value: a.method_family,
        });
      }
    }
  }

  // ── Sibling concepts ───────────────────────────────────────────────────────
  for (const c of concepts) {
    if (c.slug === rootSlug) continue;
    const cid = nodeId("concept", c.slug);

    const sharesLens = !!rootLens && c.primary_lens === rootLens;
    if (sharesLens) {
      addNode({
        id: cid,
        kind: "concept",
        slug: c.slug,
        label: c.name,
        depth: 1,
        addedBy: rootId,
      });
      addEdge(rootId, cid, {
        type: "primary_lens",
        label: "Shares primary lens",
        value: rootLens,
      });
    }

    // Concepts that measure a primitive the root also measures. Cheap to compute
    // from the primitive list (concept_slug grouping); surfaces overlap the lens
    // signal alone would miss.
    const sharedPrimitive = primitives.find(
      (p) => p.concept_slug === c.slug && measuredByRoot.has(p.slug),
    );
    if (sharedPrimitive) {
      // Only materialise the node if not already present via the lens signal.
      addNode({
        id: cid,
        kind: "concept",
        slug: c.slug,
        label: c.name,
        depth: 1,
        addedBy: rootId,
      });
      addEdge(rootId, cid, {
        type: "shared_measurement",
        label: "Shares a measurement primitive",
        value: sharedPrimitive.slug,
      });
    }
  }

  return finalize(nodes, edges);
}

function finalize(nodes: Map<string, NetNode>, edges: Map<string, NetEdge>): NetworkGraph {
  const nodeList = [...nodes.values()].sort((a, b) => a.id.localeCompare(b.id));
  const edgeList = [...edges.values()].sort((a, b) => a.id.localeCompare(b.id));
  return { nodes: nodeList, edges: edgeList };
}

/**
 * Pattern detection — group every (signal type + value) across all edges and
 * return the edge ids that belong to a value shared by `minShare`+ edges. The
 * renderer thickens these to mark a likely cluster (e.g. "3 concepts share lens
 * platform_throughput"). Pure so it's testable; the modal calls it after every
 * expand/collapse.
 */
export function detectPatterns(edges: NetEdge[], minShare = 3): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const e of edges) {
    for (const s of e.signals) {
      if (!s.value) continue;
      const key = `${s.type}::${s.value.toLowerCase()}`;
      const list = groups.get(key) ?? [];
      list.push(e.id);
      groups.set(key, list);
    }
  }
  const clusters = new Map<string, string[]>();
  for (const [key, eids] of groups) {
    if (eids.length >= minShare) clusters.set(key, eids);
  }
  return clusters;
}

/**
 * Merge a freshly-derived sub-graph (from expanding `parentId`) into the live
 * graph. New nodes are stamped with their parent + depth so branch-collapse can
 * unwind them; pre-existing nodes/edges are left untouched. Returns the merged
 * graph plus the ids that were newly added (the renderer seeds those near the
 * parent so they don't fly in from the origin).
 */
export function mergeSubGraph(
  current: NetworkGraph,
  sub: NetworkGraph,
  parentId: string,
  parentDepth: number,
): { graph: NetworkGraph; addedNodeIds: string[]; addedEdgeIds: string[] } {
  const nodeById = new Map(current.nodes.map((n) => [n.id, n]));
  const edgeById = new Map(current.edges.map((e) => [e.id, e]));
  const addedNodeIds: string[] = [];
  const addedEdgeIds: string[] = [];

  // The sub-graph's own root is its depth-0 node — NOT sub.nodes[0], which after
  // finalize() is the alphabetically-first node. Edges the sub-graph drew from
  // that root are re-rooted onto the live parent node so the new branch hangs
  // off the node the user expanded.
  const subRootId = sub.nodes.find((n) => n.depth === 0)?.id ?? parentId;

  for (const n of sub.nodes) {
    if (n.id === parentId || n.id === subRootId || nodeById.has(n.id)) continue;
    const stamped: NetNode = {
      ...n,
      depth: parentDepth + 1,
      addedBy: parentId,
    };
    nodeById.set(n.id, stamped);
    addedNodeIds.push(n.id);
  }

  for (const e of sub.edges) {
    // Re-root edges that the sub-graph drew from its own root onto the parent.
    const fromIsSubRoot = e.from === subRootId;
    const from = fromIsSubRoot ? parentId : e.from;
    const remapped: NetEdge = fromIsSubRoot ? { ...e, from, id: edgeKey(from, e.to) } : e;
    if (edgeById.has(remapped.id)) {
      // Merge signals into the existing edge so re-expansion enriches it.
      const existing = edgeById.get(remapped.id);
      if (existing) {
        for (const s of remapped.signals) {
          if (!existing.signals.some((x) => x.type === s.type && x.value === s.value)) {
            existing.signals.push(s);
          }
        }
      }
      continue;
    }
    edgeById.set(remapped.id, remapped);
    addedEdgeIds.push(remapped.id);
  }

  return {
    graph: finalize(nodeById, edgeById),
    addedNodeIds,
    addedEdgeIds,
  };
}

/**
 * Remove every descendant `parentId` introduced, recursively, and the edges
 * touching them. The root (depth 0) is never removed even if a cycle points back
 * at it. Returns the pruned graph plus the removed node ids (the renderer drops
 * them from the live DataSets).
 */
export function collapseBranch(
  current: NetworkGraph,
  parentId: string,
): { graph: NetworkGraph; removedNodeIds: string[] } {
  const childrenOf = new Map<string, string[]>();
  for (const n of current.nodes) {
    if (!n.addedBy) continue;
    const kids = childrenOf.get(n.addedBy) ?? [];
    kids.push(n.id);
    childrenOf.set(n.addedBy, kids);
  }

  const toRemove = new Set<string>();
  const stack = [...(childrenOf.get(parentId) ?? [])];
  while (stack.length) {
    const cur = stack.pop();
    if (cur === undefined) continue;
    const node = current.nodes.find((n) => n.id === cur);
    if (!node || node.depth === 0 || toRemove.has(cur)) continue;
    toRemove.add(cur);
    for (const kid of childrenOf.get(cur) ?? []) stack.push(kid);
  }

  const nodes = current.nodes.filter((n) => !toRemove.has(n.id));
  const edges = current.edges.filter((e) => !toRemove.has(e.from) && !toRemove.has(e.to));
  return { graph: { nodes, edges }, removedNodeIds: [...toRemove] };
}
