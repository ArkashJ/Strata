"use client";

/**
 * NetworkGraphModal — the related-entities network view (PR14). Visualises the
 * neighbourhood around a root concept: the concept, the primitives that measure
 * it, the frameworks for its lens, and sibling concepts that share its lens or a
 * measurement. Built CLIENT-SIDE from the existing /c, /p, /f list endpoints
 * (no new backend) via the pure helper in lib/network-graph.ts.
 *
 * Interaction model (mirrors the network-graph-modal skill, adapted to React +
 * Strata tokens):
 *   - hover a node/edge   → fade everything outside the 1-hop neighbourhood;
 *                           inspector previews it (unless something is pinned)
 *   - click a node/edge   → pin the inspector (survives mouseout so the
 *                           Expand / Collapse buttons stay reachable)
 *   - Expand relations    → hydrate that node and re-derive its sub-graph,
 *                           merge it in (multi-hop walk)
 *   - Collapse branch     → drop everything the node introduced
 *   - pattern detection   → edges sharing one signal value across 3+ edges
 *                           thicken (a likely cluster)
 *
 * vis-network paints to <canvas> and can't read CSS vars, so colours are
 * resolved off :root at open via resolvePalette() — no hex is hardcoded here.
 */

import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { tierLabel } from "@/lib/format";
import {
  type NetEdge,
  type NetNode,
  type NetworkGraph,
  buildNetworkGraph,
  collapseBranch,
  detectPatterns,
  mergeSubGraph,
  nodeId,
} from "@/lib/network-graph";
import {
  conceptQuery,
  conceptsQuery,
  frameworkQuery,
  frameworksQuery,
  primitivesQuery,
} from "@/lib/queries";
import type { ConceptSummary, PrimitiveSummary } from "@/lib/schemas";
import { LEGEND, type NetworkPalette, resolvePalette } from "./palette";

interface Props {
  rootSlug: string;
  rootName: string;
  open: boolean;
  onClose: () => void;
}

type Pinned = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

// Self-contained inspector payload. Carries graph + expanded snapshots so the
// render path reads state, not refs (React 19 react-hooks/refs).
type Inspect =
  | { kind: "node"; node: NetNode; expanded: boolean; graph: NetworkGraph }
  | { kind: "edge"; edge: NetEdge; graph: NetworkGraph }
  | null;

const SIGNAL_LABEL: Record<NetEdge["signals"][number]["type"], string> = {
  primary_lens: "Shares primary lens",
  method_family: "Same method family",
  measures: "Measures this concept",
  applies_to: "Framework for this lens",
  shared_measurement: "Shares a measurement primitive",
};

const DETAIL_PATH: Record<NetNode["kind"], string> = {
  concept: "/c",
  primitive: "/p",
  framework: "/f",
};

// vis-network's typings live behind a dynamic import; keep the handle loose.
type VisNetwork = {
  destroy: () => void;
  on: (
    event: string,
    cb: (params: {
      nodes?: string[];
      edges?: string[];
      node?: string;
      edge?: string;
    }) => void,
  ) => void;
  setOptions: (opts: unknown) => void;
  stopSimulation: () => void;
  stabilize: (iterations?: number) => void;
  getConnectedEdges: (id: string) => string[];
  getPositions: (ids: string[]) => Record<string, { x: number; y: number }>;
  moveNode: (id: string, x: number, y: number) => void;
};
type VisDataSet = {
  add: (items: unknown) => void;
  update: (items: unknown) => void;
  remove: (ids: string[]) => void;
  get: (id: string) => unknown;
  forEach: (cb: (item: { id: string }) => void) => void;
};

export function NetworkGraphModal({ rootSlug, rootName, open, onClose }: Props) {
  const qc = useQueryClient();
  const canvasRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<VisNetwork | null>(null);
  const visNodesRef = useRef<VisDataSet | null>(null);
  const visEdgesRef = useRef<VisDataSet | null>(null);
  const paletteRef = useRef<NetworkPalette | null>(null);

  // The live, derived graph (React mirror of the vis DataSets) — used by the
  // inspector and by expand/collapse to recompute topology.
  const graphRef = useRef<NetworkGraph>({ nodes: [], edges: [] });
  const expandedRef = useRef<Set<string>>(new Set());
  const pinnedRef = useRef<Pinned>(null);

  const [pinned, setPinned] = useState<Pinned>(null);
  // The inspector renders purely from this state object — it carries a snapshot
  // of everything the JSX needs (graph, expanded flag) captured at pin/hover
  // time, so the render path never reads a ref. Re-set after expand/collapse so
  // it stays fresh.
  const [inspect, setInspect] = useState<Inspect>(null);
  const [status, setStatus] = useState<string>("Building graph…");
  const [busy, setBusy] = useState(false);

  // pinnedRef mirrors `pinned` for the vis-network event handlers (which close
  // over a stale render). Synced in an effect — never assigned during render.
  useEffect(() => {
    pinnedRef.current = pinned;
  }, [pinned]);

  // ── Highlight (fade everything outside a 1-hop neighbourhood) ──────────────
  const applyFade = useCallback((brightNodes: Set<string>, brightEdges: Set<string>) => {
    const net = networkRef.current;
    const nodes = visNodesRef.current;
    const edges = visEdgesRef.current;
    const pal = paletteRef.current;
    if (!net || !nodes || !edges || !pal) return;

    const nodeUpdates: unknown[] = [];
    for (const n of graphRef.current.nodes) {
      const bright = brightNodes.has(n.id);
      const isRoot = n.depth === 0;
      const paint = isRoot ? pal.rootNode : pal.node(n);
      nodeUpdates.push({
        id: n.id,
        color: paint,
        opacity: isRoot || bright ? 1 : 0.25,
      });
    }
    const edgeUpdates: unknown[] = [];
    for (const e of graphRef.current.edges) {
      const bright = brightEdges.has(e.id);
      const colour = bright ? pal.edge : pal.edgeFaded;
      edgeUpdates.push({
        id: e.id,
        color: { color: colour, highlight: colour, hover: colour },
      });
    }
    nodes.update(nodeUpdates);
    edges.update(edgeUpdates);
  }, []);

  // ── Pattern detection — thicken edges sharing one signal value (3+) ────────
  const runPatternHighlight = useCallback(() => {
    const edges = visEdgesRef.current;
    const pal = paletteRef.current;
    if (!edges || !pal) return;
    const clusters = detectPatterns(graphRef.current.edges, 3);
    const clustered = new Set<string>();
    for (const eids of clusters.values()) for (const id of eids) clustered.add(id);
    edges.update(
      graphRef.current.edges.map((e) => ({
        id: e.id,
        width: clustered.has(e.id) ? 4 : 1 + Math.min(3, e.signals.length),
      })),
    );
  }, []);

  const clearHighlight = useCallback(() => {
    const pal = paletteRef.current;
    const nodes = visNodesRef.current;
    const edges = visEdgesRef.current;
    if (!pal || !nodes || !edges) return;
    nodes.update(
      graphRef.current.nodes.map((n) => ({
        id: n.id,
        color: n.depth === 0 ? pal.rootNode : pal.node(n),
        opacity: 1,
      })),
    );
    edges.update(
      graphRef.current.edges.map((e) => ({
        id: e.id,
        color: { color: pal.edge, highlight: pal.edge, hover: pal.edge },
      })),
    );
    // Re-thicken clusters after restoring base colours.
    runPatternHighlight();
  }, [runPatternHighlight]);

  const highlightNode = useCallback(
    (id: string) => {
      const net = networkRef.current;
      if (!net) return;
      const connected = net.getConnectedEdges(id);
      const bright = new Set<string>([id]);
      for (const eid of connected) {
        const e = graphRef.current.edges.find((x) => x.id === eid);
        if (e) {
          bright.add(e.from);
          bright.add(e.to);
        }
      }
      applyFade(bright, new Set(connected));
    },
    [applyFade],
  );

  const highlightEdge = useCallback(
    (eid: string) => {
      const e = graphRef.current.edges.find((x) => x.id === eid);
      if (!e) return;
      applyFade(new Set([e.from, e.to]), new Set([eid]));
    },
    [applyFade],
  );

  const reapplyPin = useCallback(() => {
    const p = pinnedRef.current;
    if (!p) return;
    if (p.kind === "node") highlightNode(p.id);
    else highlightEdge(p.id);
  }, [highlightNode, highlightEdge]);

  // Build the self-contained inspector payload from a node/edge id, snapshotting
  // the current graph + expanded set. Called only from event handlers / effects
  // (never during render), so reading refs here is safe.
  const buildInspect = useCallback((kind: "node" | "edge", id: string): Inspect => {
    const graph = graphRef.current;
    if (kind === "node") {
      const node = graph.nodes.find((n) => n.id === id);
      if (!node) return null;
      return {
        kind: "node",
        node,
        expanded: expandedRef.current.has(id),
        graph,
      };
    }
    const edge = graph.edges.find((e) => e.id === id);
    if (!edge) return null;
    return { kind: "edge", edge, graph };
  }, []);

  // ── Render the live graph into the vis DataSets ────────────────────────────
  const renderGraph = useCallback((graph: NetworkGraph) => {
    const nodes = visNodesRef.current;
    const edges = visEdgesRef.current;
    const pal = paletteRef.current;
    if (!nodes || !edges || !pal) return;
    graphRef.current = graph;

    nodes.update(
      graph.nodes.map((n) => {
        const isRoot = n.depth === 0;
        const paint = isRoot ? pal.rootNode : pal.node(n);
        return {
          id: n.id,
          label: truncate(n.label, isRoot ? 28 : 24),
          shape: isRoot ? "circle" : "dot",
          color: paint,
          size: isRoot ? 26 : 12,
          borderWidth: isRoot ? 3 : 2,
          font: isRoot
            ? {
                color: pal.labelOnDark,
                size: 13,
                face: "system-ui, sans-serif",
                strokeWidth: 0,
              }
            : {
                color: pal.labelOnLight,
                size: 11,
                face: "system-ui, sans-serif",
                strokeWidth: 3,
                strokeColor: pal.labelStroke,
              },
          widthConstraint: isRoot ? { maximum: 130 } : undefined,
          margin: isRoot ? { top: 10, right: 10, bottom: 10, left: 10 } : undefined,
        };
      }),
    );
    edges.update(
      graph.edges.map((e) => ({
        id: e.id,
        from: e.from,
        to: e.to,
        width: 1 + Math.min(3, e.signals.length),
        color: { color: pal.edge, highlight: pal.edge, hover: pal.edge },
        smooth: { enabled: true, type: "dynamic", roundness: 0.5 },
      })),
    );
  }, []);

  // ── Initial build (open) ───────────────────────────────────────────────────
  // Deps are intentionally [open, rootSlug] only: this effect builds the entire
  // vis-network once per open and wires its event handlers. Adding the
  // referenced callbacks would tear down and rebuild the network on every
  // render (they're recreated when status/busy change), losing layout and
  // pins. The handlers read live state through refs, so a stale closure here is
  // the intended design, not a bug.
  // biome-ignore lint/correctness/useExhaustiveDependencies: see comment above — one-shot network build
  useEffect(() => {
    if (!open || !canvasRef.current) return;
    let mounted = true;

    async function init() {
      setStatus("Building graph…");
      setBusy(true);
      // Fetch the three list endpoints + the hydrated root concept in parallel.
      // ensureQueryData reuses anything already in the TanStack cache from the
      // detail page, so opening the modal is usually instant.
      const [concepts, primitives, frameworks, rootDetail] = await Promise.all([
        qc.ensureQueryData(conceptsQuery),
        qc.ensureQueryData(primitivesQuery),
        qc.ensureQueryData(frameworksQuery),
        qc.ensureQueryData(conceptQuery(rootSlug)).catch(() => null),
      ]);
      if (!mounted || !canvasRef.current) return;

      const { Network, DataSet } = await import("vis-network/standalone");
      if (!mounted || !canvasRef.current) return;

      paletteRef.current = resolvePalette();
      const graph = buildNetworkGraph({
        rootSlug,
        concepts,
        primitives,
        frameworks,
        rootDetail: rootDetail ? { measurements: rootDetail.measurements } : null,
      });
      graphRef.current = graph;
      expandedRef.current = new Set([nodeId0(graph)]);

      const visNodes = new DataSet([]) as unknown as VisDataSet;
      const visEdges = new DataSet([]) as unknown as VisDataSet;
      visNodesRef.current = visNodes;
      visEdgesRef.current = visEdges;

      const network = new Network(
        // biome-ignore lint/style/noNonNullAssertion: guarded above
        canvasRef.current!,
        { nodes: visNodes as never, edges: visEdges as never },
        {
          nodes: { shape: "dot", borderWidth: 2 },
          edges: {
            width: 1.5,
            smooth: { enabled: true, type: "dynamic", roundness: 0.5 },
          },
          physics: {
            solver: "barnesHut",
            barnesHut: {
              gravitationalConstant: -8000,
              centralGravity: 0.2,
              springLength: 180,
              springConstant: 0.04,
              damping: 0.4,
              avoidOverlap: 0.6,
            },
            stabilization: { iterations: 300, fit: true },
          },
          interaction: {
            hover: true,
            tooltipDelay: 120,
            navigationButtons: true,
          },
        },
      ) as unknown as VisNetwork;
      networkRef.current = network;

      renderGraph(graph);
      runPatternHighlight();

      // Freeze the sim whenever it has a chance to settle — barnes-hut otherwise
      // integrates forever and the graph drifts on every hover. restabilize()
      // flips physics back on for a bounded burst when new nodes arrive.
      const freezeSim = () => {
        try {
          network.stopSimulation();
        } catch (_) {}
        network.setOptions({ physics: { enabled: false } });
      };
      network.on("stabilizationIterationsDone", freezeSim);
      network.on("stabilized", freezeSim);
      network.on("dragEnd", freezeSim);

      // Pin model handled entirely at the call site (no effect mirrors
      // `pinned`): clicking toggles the pin, sets the highlight, and snapshots
      // the inspector payload in one place.
      const pinTo = (kind: "node" | "edge", id: string) => {
        const prev = pinnedRef.current;
        const alreadyPinned = prev && prev.kind === kind && prev.id === id;
        if (alreadyPinned) {
          setPinned(null);
          clearHighlight();
          setInspect(null);
          return;
        }
        setPinned({ kind, id } as Pinned);
        if (kind === "node") highlightNode(id);
        else highlightEdge(id);
        setInspect(buildInspect(kind, id));
      };

      network.on("click", (p) => {
        if (p.nodes?.length) {
          pinTo("node", String(p.nodes[0]));
          return;
        }
        if (p.edges?.length) {
          pinTo("edge", String(p.edges[0]));
          return;
        }
        setPinned(null);
        clearHighlight();
        setInspect(null);
      });

      network.on("hoverNode", (p) => {
        const id = String(p.node);
        highlightNode(id);
        if (!pinnedRef.current) setInspect(buildInspect("node", id));
      });
      network.on("hoverEdge", (p) => {
        const id = String(p.edge);
        highlightEdge(id);
        if (!pinnedRef.current) setInspect(buildInspect("edge", id));
      });
      network.on("blurNode", () => {
        if (pinnedRef.current) reapplyPin();
        else {
          clearHighlight();
          setInspect(null);
        }
      });
      network.on("blurEdge", () => {
        if (pinnedRef.current) reapplyPin();
        else {
          clearHighlight();
          setInspect(null);
        }
      });

      setBusy(false);
      setStatus(
        graph.nodes.length > 1
          ? `${graph.nodes.length - 1} related ${graph.nodes.length === 2 ? "entity" : "entities"}.`
          : "No related entities found for this concept.",
      );
    }

    init().catch((e) => {
      console.error("network graph init failed", e);
      if (mounted) {
        setBusy(false);
        setStatus("Could not load the related-entity network.");
      }
    });

    return () => {
      mounted = false;
      networkRef.current?.destroy();
      networkRef.current = null;
      visNodesRef.current = null;
      visEdgesRef.current = null;
    };
    // Deps are [open, rootSlug] by design — see the block comment above the
    // effect. The referenced callbacks are read through stable closures/refs;
    // adding them would rebuild the whole network on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, rootSlug]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  // ── Expand / collapse (multi-hop walk) ─────────────────────────────────────
  const expand = useCallback(
    async (node: NetNode) => {
      if (expandedRef.current.has(node.id) || busy) return;
      const net = networkRef.current;
      if (!net) return;
      setBusy(true);
      setStatus(`Expanding ${node.label}…`);
      try {
        const [concepts, primitives, frameworks] = await Promise.all([
          qc.ensureQueryData(conceptsQuery),
          qc.ensureQueryData(primitivesQuery),
          qc.ensureQueryData(frameworksQuery),
        ]);

        // A framework node expands by hydrating its detail and attaching the
        // concepts it is applicable_to; concept/primitive nodes re-root the pure
        // builder at their slug.
        let sub: NetworkGraph;
        if (node.kind === "framework") {
          sub = await frameworkSubGraph(node, qc, concepts);
        } else if (node.kind === "concept") {
          const detail = await qc.ensureQueryData(conceptQuery(node.slug)).catch(() => null);
          sub = buildNetworkGraph({
            rootSlug: node.slug,
            concepts,
            primitives,
            frameworks,
            rootDetail: detail ? { measurements: detail.measurements } : null,
          });
        } else {
          // Primitive: surface the concepts that measure it (its concept_slug
          // owner is already linked; this adds cross-concept reuse).
          sub = primitiveSubGraph(node, concepts, primitives);
        }

        const parentDepth = graphRef.current.nodes.find((n) => n.id === node.id)?.depth ?? 1;
        const { graph, addedNodeIds } = mergeSubGraph(graphRef.current, sub, node.id, parentDepth);
        expandedRef.current.add(node.id);
        renderGraph(graph);

        // Seed new children near the parent so they don't fly in from origin.
        if (addedNodeIds.length) {
          const pos = net.getPositions([node.id])[node.id];
          if (pos) {
            for (const id of addedNodeIds) {
              try {
                net.moveNode(
                  id,
                  pos.x + (Math.random() - 0.5) * 60,
                  pos.y + (Math.random() - 0.5) * 60,
                );
              } catch (_) {}
            }
          }
          net.setOptions({ physics: { enabled: true } });
          net.stabilize(200);
        }
        runPatternHighlight();
        reapplyPin();
        // Re-snapshot the inspector so its `expanded` flag + graph reflect the
        // freshly expanded branch.
        setInspect(buildInspect("node", node.id));
        setStatus(
          addedNodeIds.length
            ? `Added ${addedNodeIds.length} related to ${node.label}.`
            : `${node.label} has no further related entities.`,
        );
      } catch (e) {
        console.error("expand failed", e);
        setStatus(`Failed to expand ${node.label}.`);
      } finally {
        setBusy(false);
      }
    },
    [busy, qc, renderGraph, reapplyPin, runPatternHighlight, buildInspect],
  );

  const collapse = useCallback(
    (node: NetNode) => {
      const nodes = visNodesRef.current;
      if (!nodes) return;
      const { graph, removedNodeIds } = collapseBranch(graphRef.current, node.id);
      expandedRef.current.delete(node.id);
      for (const id of removedNodeIds) expandedRef.current.delete(id);
      if (removedNodeIds.length) nodes.remove(removedNodeIds);
      graphRef.current = graph;
      renderGraph(graph);
      runPatternHighlight();
      reapplyPin();
      // Re-snapshot so the inspector's `expanded` flag flips back and its graph
      // no longer references the pruned nodes.
      setInspect(buildInspect("node", node.id));
      setStatus(`Collapsed branch from ${node.label} (${removedNodeIds.length} removed).`);
    },
    [renderGraph, reapplyPin, runPatternHighlight, buildInspect],
  );

  const unpin = useCallback(() => {
    setPinned(null);
    clearHighlight();
    setInspect(null);
  }, [clearHighlight]);

  if (!open) return null;

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: backdrop dismiss; Escape handled above
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center p-[2vw]"
      style={{ background: "rgba(10,10,11,0.55)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Native <dialog open> — the modality/backdrop is hand-managed (overflow
			    lock + the presentation backdrop above), so we use the `open`
			    attribute rather than showModal() to avoid the top-layer stealing
			    focus from the canvas. */}
      <dialog
        open
        aria-modal="true"
        aria-label={`Related-entity network for ${rootName}`}
        className="flex w-full max-w-[1280px] flex-col overflow-hidden rounded-[var(--r-4)] bg-[var(--bg-1)] text-[var(--fg-1)] shadow-[var(--shadow-overlay)]"
        style={{ position: "static", height: "min(720px, 92vh)", padding: 0 }}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-1)] px-5 py-3">
          <div className="min-w-0">
            <h2 className="display text-[18px] text-[var(--fg-1)]">Related-entity network</h2>
            <p className="truncate text-[12px] text-[var(--fg-3)]">
              Neighbourhood of <span className="text-[var(--fg-2)]">{rootName}</span> · hover a line
              to see the shared signal, click a node to pin it.
            </p>
          </div>
          <Button variant="ghost" sm onClick={onClose} aria-label="Close network view">
            Close ✕
          </Button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          {/* Canvas */}
          <div className="relative min-h-[280px] flex-1" style={{ background: "var(--canvas-bg)" }}>
            <div ref={canvasRef} className="h-full w-full" />
            <output
              aria-live="polite"
              className="pointer-events-none absolute bottom-3 left-4 right-4 truncate text-[11px] text-[var(--fg-2)]"
            >
              {status}
            </output>
            <div className="absolute left-4 top-3 flex flex-wrap gap-3 text-[10px] text-[var(--fg-3)]">
              {LEGEND.map((l) => (
                <span key={l.label} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: `var(${l.cssVar})` }}
                  />
                  {l.label}
                </span>
              ))}
              <span className="flex items-center gap-1">
                <span
                  className="inline-block h-[3px] w-4"
                  style={{ background: "var(--danger)" }}
                />
                Shared-signal cluster
              </span>
            </div>
          </div>

          {/* Inspector */}
          <aside className="flex w-full shrink-0 flex-col border-t border-[var(--border-1)] md:w-[var(--right-rail-w)] md:border-l md:border-t-0">
            <div className="border-b border-[var(--border-1)] px-4 py-3">
              <span className="text-[13px] font-medium text-[var(--fg-1)]">Inspector</span>
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-3 text-[13px]">
              {inspect?.kind === "node" ? (
                <NodeInspector
                  node={inspect.node}
                  pinned={pinned?.kind === "node" && pinned.id === inspect.node.id}
                  expanded={inspect.expanded}
                  busy={busy}
                  graph={inspect.graph}
                  onExpand={() => expand(inspect.node)}
                  onCollapse={() => collapse(inspect.node)}
                  onUnpin={unpin}
                />
              ) : inspect?.kind === "edge" ? (
                <EdgeInspector edge={inspect.edge} graph={inspect.graph} />
              ) : (
                <div className="mt-8 text-center text-[var(--fg-3)]">
                  <p className="text-[14px]">Hover or click a node</p>
                  <p className="mt-1 text-[12px]">to inspect what connects it</p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </dialog>
    </div>
  );
}

// ── Inspector subviews ────────────────────────────────────────────────────────

function NodeInspector({
  node,
  pinned,
  expanded,
  busy,
  graph,
  onExpand,
  onCollapse,
  onUnpin,
}: {
  node: NetNode;
  pinned: boolean;
  expanded: boolean;
  busy: boolean;
  graph: NetworkGraph;
  onExpand: () => void;
  onCollapse: () => void;
  onUnpin: () => void;
}) {
  const isRoot = node.depth === 0;
  const connected = graph.edges.filter((e) => e.from === node.id || e.to === node.id);
  const incoming = graph.edges.find((e) => e.to === node.id || e.from === node.id);

  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <span
          className="inline-block h-3 w-3 rounded-full"
          style={{ background: `var(${kindVar(node)})` }}
        />
        <span className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          {node.kind}
          {node.subKind ? ` · ${tierLabel(node.subKind)}` : ""}
        </span>
        {pinned ? (
          <span className="rounded-full bg-[var(--accent-tint)] px-1.5 py-0.5 text-[10px] text-[var(--accent)]">
            pinned
          </span>
        ) : null}
      </div>

      <h3 className="mt-1 text-[15px] font-medium leading-tight text-[var(--fg-1)]">
        {node.label}
      </h3>
      <p className="mt-0.5 font-mono text-[11px] text-[var(--fg-3)]">
        {node.slug}
        {node.depth ? ` · depth ${node.depth}` : ""}
      </p>

      {!isRoot && incoming ? (
        <div className="mt-3">
          <div className="mb-1 text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
            Why related
          </div>
          <ul className="flex flex-col gap-1 text-[12px] text-[var(--fg-2)]">
            {connected.flatMap((e) =>
              e.signals.map((s) => (
                <li key={`${e.id}-${s.type}-${s.value ?? ""}`} className="flex items-start gap-1.5">
                  <span className="font-medium text-[var(--accent)]">
                    {SIGNAL_LABEL[s.type] ?? s.label}
                  </span>
                  {s.value ? <span className="text-[var(--fg-3)]">— {s.value}</span> : null}
                </li>
              )),
            )}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={`${DETAIL_PATH[node.kind]}/${encodeURIComponent(node.slug)}`} target="_blank">
          <Button sm>Open page →</Button>
        </Link>
        {isRoot ? null : expanded ? (
          <Button variant="ghost" sm onClick={onCollapse} disabled={busy}>
            Collapse branch
          </Button>
        ) : (
          <Button variant="ghost" sm onClick={onExpand} disabled={busy}>
            Expand relations
          </Button>
        )}
        {pinned ? (
          <Button variant="ghost" sm onClick={onUnpin}>
            Unpin
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function EdgeInspector({
  edge,
  graph,
}: {
  edge: NetEdge;
  graph: NetworkGraph;
}) {
  const from = graph.nodes.find((n) => n.id === edge.from);
  const to = graph.nodes.find((n) => n.id === edge.to);
  return (
    <div>
      <div className="mb-2 text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
        Connection
      </div>
      <div className="flex items-center gap-2 text-[13px] text-[var(--fg-1)]">
        <span className="truncate font-medium">{from?.label ?? edge.from}</span>
        <span className="text-[var(--fg-4)]">↔</span>
        <span className="truncate font-medium">{to?.label ?? edge.to}</span>
      </div>
      <div className="mt-3">
        <div className="mb-2 text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          Shared signals
        </div>
        <ul className="flex flex-col gap-1 text-[12px] text-[var(--fg-2)]">
          {edge.signals.map((s) => (
            <li key={`${s.type}-${s.value ?? ""}`} className="flex items-start gap-1.5">
              <span className="font-medium text-[var(--accent)]">
                {SIGNAL_LABEL[s.type] ?? s.label}
              </span>
              {s.value ? <span className="text-[var(--fg-3)]">— {s.value}</span> : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ── Sub-graph builders for expansion ────────────────────────────────────────

// A framework's neighbourhood = the concepts it's applicable_to. applicable_to
// is only on the detail record, so hydrate it; emit a sub-graph rooted at the
// framework node so mergeSubGraph re-roots its edges onto the live node.
async function frameworkSubGraph(
  node: NetNode,
  qc: QueryClient,
  concepts: ConceptSummary[],
): Promise<NetworkGraph> {
  const detail = await qc.ensureQueryData(frameworkQuery(node.slug)).catch(() => null);
  const nodes: NetNode[] = [{ ...node, depth: 0, addedBy: undefined }];
  const edges: NetEdge[] = [];
  for (const slug of detail?.applicable_to ?? []) {
    const c = concepts.find((x) => x.slug === slug);
    if (!c) continue;
    const cid = nodeId("concept", slug);
    nodes.push({ id: cid, kind: "concept", slug, label: c.name, depth: 1 });
    edges.push({
      id: `${node.id}__${cid}`,
      from: node.id,
      to: cid,
      signals: [
        {
          type: "applies_to",
          label: "Applies to this concept",
          value: node.slug,
        },
      ],
    });
  }
  return { nodes, edges };
}

// A primitive's neighbourhood = every concept that measures it (cross-concept
// reuse beyond its owning concept_slug). Rooted at the primitive node.
function primitiveSubGraph(
  node: NetNode,
  concepts: ConceptSummary[],
  primitives: PrimitiveSummary[],
): NetworkGraph {
  const owners = new Set(primitives.filter((p) => p.slug === node.slug).map((p) => p.concept_slug));
  const nodes: NetNode[] = [{ ...node, depth: 0, addedBy: undefined }];
  const edges: NetEdge[] = [];
  for (const c of concepts) {
    if (!owners.has(c.slug)) continue;
    const cid = nodeId("concept", c.slug);
    nodes.push({
      id: cid,
      kind: "concept",
      slug: c.slug,
      label: c.name,
      depth: 1,
    });
    edges.push({
      id: `${node.id}__${cid}`,
      from: node.id,
      to: cid,
      signals: [
        {
          type: "measures",
          label: "Measured by this concept",
          value: node.slug,
        },
      ],
    });
  }
  return { nodes, edges };
}

function kindVar(node: NetNode): string {
  if (node.kind === "concept") return "--accent";
  if (node.kind === "framework") return "--tier-analyst";
  return node.subKind === "composite_primitive" ? "--tier-aggregator" : "--tier-regulator";
}

// First node id in a freshly-built graph is the root (sorted, but the root is
// stamped depth 0 — find it rather than assume index 0 after sort).
function nodeId0(graph: NetworkGraph): string {
  return graph.nodes.find((n) => n.depth === 0)?.id ?? graph.nodes[0]?.id ?? "";
}

function truncate(raw: string, n: number): string {
  const s = (raw || "").trim();
  return s.length <= n ? s : `${s.slice(0, n - 1)}…`;
}
