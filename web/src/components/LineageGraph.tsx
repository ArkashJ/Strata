"use client";

import { formatUSD } from "@/lib/format";
import type { TAMOutput } from "@/lib/schemas";
import { useCallback, useEffect, useRef, useState } from "react";

type NodeKind = "concept" | "framework" | "primitive";

interface GraphNode {
  id: string;
  label: string;
  kind: NodeKind;
  method_family?: string;
  role?: string;
  value?: number;
  lens?: string;
}

interface GraphEdge {
  id: string;
  from: string;
  to: string;
  signals: string[];
}

interface PinnedState {
  kind: "node" | "edge";
  id: string;
}

const KIND_COLOURS: Record<NodeKind, { background: string; border: string }> = {
  concept: { background: "#5b5bd6", border: "#4848c4" },
  framework: { background: "#3fa66b", border: "#2d8a55" },
  primitive: { background: "#c99846", border: "#a87d35" },
};

const METHOD_COLOURS: Record<string, { background: string; border: string }> = {
  top_down_spend: { background: "#3fa66b", border: "#2d8a55" },
  bottoms_up_seats: { background: "#5b5bd6", border: "#4848c4" },
  comparable_revenue: { background: "#2ba39a", border: "#1e8c84" },
  analog_penetration: { background: "#c99846", border: "#a87d35" },
  value_chain: { background: "#8b5cd6", border: "#7044c0" },
};

interface Props {
  tam: TAMOutput;
  open: boolean;
  onClose: () => void;
}

export function LineageGraph({ tam, open, onClose }: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<unknown>(null);
  const [pinned, setPinned] = useState<PinnedState | null>(null);
  const [detail, setDetail] = useState<GraphNode | null>(null);
  const [edgeDetail, setEdgeDetail] = useState<GraphEdge | null>(null);
  const graphDataRef = useRef<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({
    nodes: [],
    edges: [],
  });

  const buildGraphData = useCallback(() => {
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];
    const primitiveSet = new Set<string>();

    const values = tam.scenarios.map((s) => s.value);
    const midpoint = values.reduce((a, b) => a + b, 0) / values.length;

    nodes.push({
      id: "concept",
      label: truncate(tam.target.concept, 28),
      kind: "concept",
      value: midpoint,
    });

    for (const scenario of tam.scenarios) {
      const fId = `f-${scenario.framework}`;
      nodes.push({
        id: fId,
        label: truncate(scenario.definition, 26),
        kind: "framework",
        lens: scenario.lens,
        value: scenario.value,
      });
      edges.push({
        id: `concept__${fId}`,
        from: "concept",
        to: fId,
        signals: [`lens: ${scenario.lens.replace(/_/g, " ")}`],
      });

      for (const input of scenario.inputs_used) {
        const pId = `p-${input.primitive_slug}`;
        if (!primitiveSet.has(pId)) {
          primitiveSet.add(pId);
          nodes.push({
            id: pId,
            label: truncate(input.role_name, 24),
            kind: "primitive",
            role: input.role,
          });
        }
        edges.push({
          id: `${fId}__${pId}`,
          from: fId,
          to: pId,
          signals: [`role: ${input.role.replace(/_/g, " ")}`],
        });
      }
    }

    graphDataRef.current = { nodes, edges };
    setGraphData({ nodes, edges });
    return { nodes, edges };
  }, [tam]);

  useEffect(() => {
    if (!open || !canvasRef.current) return;

    let mounted = true;

    async function init() {
      const { Network, DataSet } = await import("vis-network/standalone");
      if (!mounted || !canvasRef.current) return;

      const { nodes, edges } = buildGraphData();

      const primEdgeCount = new Map<string, number>();
      for (const e of edges) {
        if (e.to.startsWith("p-")) {
          primEdgeCount.set(e.to, (primEdgeCount.get(e.to) ?? 0) + 1);
        }
      }
      const sharedPrimitives = new Set<string>();
      for (const [pId, count] of primEdgeCount) {
        if (count >= 2) sharedPrimitives.add(pId);
      }

      const visNodes = new DataSet(
        nodes.map((n) => {
          const isRoot = n.kind === "concept";
          const colour =
            n.kind === "framework" && n.lens
              ? (METHOD_COLOURS[n.lens] ?? KIND_COLOURS.framework)
              : KIND_COLOURS[n.kind];
          return {
            id: n.id,
            label: n.label,
            shape: isRoot ? ("circle" as const) : ("dot" as const),
            color: colour,
            size: isRoot
              ? 30
              : n.kind === "framework"
                ? 18
                : 12 + (sharedPrimitives.has(n.id) ? 4 : 0),
            font: isRoot
              ? { color: "#fff", size: 13, face: "system-ui, sans-serif", strokeWidth: 0 }
              : {
                  size: 11,
                  face: "system-ui, sans-serif",
                  color: "#1f2937",
                  strokeWidth: 3,
                  strokeColor: "#ffffff",
                },
            borderWidth: isRoot ? 3 : sharedPrimitives.has(n.id) ? 3 : 2,
            widthConstraint: isRoot ? { maximum: 130 } : undefined,
            margin: isRoot ? { top: 10, right: 10, bottom: 10, left: 10 } : undefined,
          };
        }),
      );

      const visEdges = new DataSet(
        edges.map((e) => ({
          id: e.id,
          from: e.from,
          to: e.to,
          width: sharedPrimitives.has(e.to) ? 3 : 1.5,
          color: {
            color: sharedPrimitives.has(e.to) ? "#e5484d" : "#94a3b8",
            highlight: "#1E3A5F",
            hover: "#1E3A5F",
          },
          smooth: { enabled: true, type: "dynamic", roundness: 0.5 },
        })),
      );

      const network = new Network(
        // biome-ignore lint/style/noNonNullAssertion: guarded by `if (!canvasRef.current) return` above
        canvasRef.current!,
        { nodes: visNodes, edges: visEdges },
        {
          nodes: { shape: "dot", borderWidth: 2 },
          edges: { width: 1.5, smooth: { enabled: true, type: "dynamic", roundness: 0.5 } },
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
          interaction: { hover: true, tooltipDelay: 120, navigationButtons: true },
        },
      );

      const freezeSim = () => {
        try {
          network.stopSimulation();
        } catch (_) {}
        network.setOptions({ physics: { enabled: false } });
      };
      network.on("stabilizationIterationsDone", freezeSim);
      network.on("stabilized", freezeSim);
      network.on("dragEnd", freezeSim);

      network.on("click", (params: { nodes?: string[]; edges?: string[] }) => {
        if (params.nodes?.length) {
          const id = String(params.nodes[0]);
          const node = graphDataRef.current.nodes.find((nd) => nd.id === id);
          if (node) {
            setPinned({ kind: "node", id });
            setDetail(node);
            setEdgeDetail(null);
          }
          return;
        }
        if (params.edges?.length) {
          const eid = String(params.edges[0]);
          const edge = graphDataRef.current.edges.find((ed) => ed.id === eid);
          if (edge) {
            setPinned({ kind: "edge", id: eid });
            setEdgeDetail(edge);
            setDetail(null);
          }
          return;
        }
        setPinned(null);
        setDetail(null);
        setEdgeDetail(null);
      });

      network.on("hoverNode", (params: { node: string }) => {
        if (!mounted) return;
        const n = graphDataRef.current.nodes.find((nd) => nd.id === String(params.node));
        if (n) setDetail(n);
      });

      network.on("hoverEdge", (params: { edge: string }) => {
        if (!mounted) return;
        const e = graphDataRef.current.edges.find((ed) => ed.id === String(params.edge));
        if (e) setEdgeDetail(e);
      });

      networkRef.current = network;
    }

    init();

    return () => {
      mounted = false;
      if (networkRef.current) {
        (networkRef.current as { destroy: () => void }).destroy();
        networkRef.current = null;
      }
    };
  }, [open, buildGraphData]);

  useEffect(() => {
    if (!open) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  if (!open) return null;

  const sharedPrimitives = new Set<string>();
  const primUsageCount = new Map<string, string[]>();
  for (const e of graphData.edges) {
    if (e.to.startsWith("p-") && e.from.startsWith("f-")) {
      const fws = primUsageCount.get(e.to) ?? [];
      fws.push(e.from);
      primUsageCount.set(e.to, fws);
    }
  }
  for (const [pId, fws] of primUsageCount) {
    if (fws.length >= 2) sharedPrimitives.add(pId);
  }

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: backdrop dismiss, Escape handled by useEffect above
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Lineage network"
        className="bg-[var(--bg-1)] rounded-[var(--r-4)] shadow-[var(--shadow-overlay)] flex overflow-hidden"
        style={{ width: "min(1100px, 95vw)", height: "min(700px, 85vh)" }}
      >
        <div className="flex-1 relative" style={{ background: "var(--canvas-bg)" }}>
          <div className="absolute top-3 left-4 z-10 flex items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--fg-3)]">
              Lineage network
            </span>
          </div>
          <div ref={canvasRef} className="w-full h-full" />
          <div className="absolute bottom-3 left-4 right-4 flex gap-3 text-[10px] text-[var(--fg-3)]">
            <Legend colour="#5b5bd6" label="Concept" />
            <Legend colour="#3fa66b" label="Framework" />
            <Legend colour="#c99846" label="Primitive" />
            <span className="ml-2 flex items-center gap-1">
              <span className="inline-block w-4 h-[2px] bg-[#e5484d]" /> shared input
            </span>
          </div>
        </div>

        <div className="w-[320px] shrink-0 border-l border-[var(--border-1)] flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-1)]">
            <span className="text-[13px] font-medium text-[var(--fg-1)]">Inspector</span>
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              className="w-7 h-7 flex items-center justify-center rounded-[var(--r-2)]
                         text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 text-[13px]">
            {detail ? (
              <NodeDetail
                node={detail}
                pinned={pinned?.kind === "node" && pinned.id === detail.id}
                sharedPrimitives={sharedPrimitives}
                edges={graphData.edges}
                nodes={graphData.nodes}
              />
            ) : edgeDetail ? (
              <EdgeDetail edge={edgeDetail} nodes={graphData.nodes} />
            ) : (
              <div className="text-[var(--fg-3)] text-center mt-8">
                <p className="text-[14px]">Hover or click a node</p>
                <p className="text-[12px] mt-1">to inspect its lineage</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function NodeDetail({
  node,
  pinned,
  sharedPrimitives,
  edges,
  nodes,
}: {
  node: GraphNode;
  pinned: boolean;
  sharedPrimitives: Set<string>;
  edges: GraphEdge[];
  nodes: GraphNode[];
}) {
  const isShared = sharedPrimitives.has(node.id);
  const connectedEdges = edges.filter((e) => e.from === node.id || e.to === node.id);
  const connectedNodes = connectedEdges
    .map((e) => nodes.find((n) => n.id === (e.from === node.id ? e.to : e.from)))
    .filter(Boolean) as GraphNode[];

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span
          className="inline-block w-3 h-3 rounded-full"
          style={{ background: KIND_COLOURS[node.kind].background }}
        />
        <span className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          {node.kind}
        </span>
        {pinned && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--accent-tint)] text-[var(--accent)]">
            pinned
          </span>
        )}
      </div>

      <h3 className="text-[15px] font-medium text-[var(--fg-1)] mt-1 leading-tight">
        {node.label}
      </h3>

      {node.value !== undefined && (
        <div className="tam-num text-[20px] text-[var(--fg-1)] mt-2">{formatUSD(node.value)}</div>
      )}

      {node.lens && (
        <div className="mt-2">
          <span className="role-chip uppercase tracking-[0.04em]">
            {node.lens.replace(/_/g, " ")}
          </span>
        </div>
      )}

      {node.role && (
        <div className="mt-2">
          <span className="role-chip">{node.role.replace(/_/g, " ")}</span>
        </div>
      )}

      {isShared && (
        <div className="mt-3 px-3 py-2 rounded-[var(--r-2)] bg-[rgba(229,72,77,0.08)] text-[12px] text-[#e5484d]">
          Shared across {connectedEdges.filter((e) => e.from.startsWith("f-")).length} frameworks —
          affects independence score
        </div>
      )}

      {connectedNodes.length > 0 && (
        <div className="mt-4">
          <div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)] mb-2">
            Connected to
          </div>
          <ul className="flex flex-col gap-1">
            {connectedNodes.map((cn) => (
              <li key={cn.id} className="flex items-center gap-2 text-[12px] text-[var(--fg-2)]">
                <span
                  className="inline-block w-2 h-2 rounded-full shrink-0"
                  style={{ background: KIND_COLOURS[cn.kind].background }}
                />
                {cn.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {connectedEdges.length > 0 && (
        <div className="mt-4">
          <div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)] mb-2">
            Signals
          </div>
          <ul className="flex flex-col gap-1 text-[12px] text-[var(--fg-2)]">
            {connectedEdges.flatMap((e) =>
              e.signals.map((s) => (
                <li key={`${e.id}-${s}`} className="flex items-center gap-1.5">
                  <span className="text-[var(--fg-4)]">·</span> {s}
                </li>
              )),
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function EdgeDetail({ edge, nodes }: { edge: GraphEdge; nodes: GraphNode[] }) {
  const fromNode = nodes.find((n) => n.id === edge.from);
  const toNode = nodes.find((n) => n.id === edge.to);
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)] mb-2">
        Connection
      </div>
      <div className="flex items-center gap-2 text-[13px] text-[var(--fg-1)]">
        <span className="font-medium">{fromNode?.label ?? edge.from}</span>
        <span className="text-[var(--fg-4)]">→</span>
        <span className="font-medium">{toNode?.label ?? edge.to}</span>
      </div>
      {edge.signals.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)] mb-2">
            Signals
          </div>
          <ul className="flex flex-col gap-1 text-[12px] text-[var(--fg-2)]">
            {edge.signals.map((s) => (
              <li key={s} className="flex items-center gap-1.5">
                <span className="text-[var(--fg-4)]">·</span> {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Legend({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: colour }} />
      {label}
    </span>
  );
}

function truncate(raw: string, n: number): string {
  const s = (raw || "").trim();
  if (s.length <= n) return s;
  return `${s.slice(0, n - 1)}…`;
}
