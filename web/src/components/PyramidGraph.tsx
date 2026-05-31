"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  type NodeTypes,
  Position,
  ReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";

import { GhostCard, type MenuAnchor, NodeContextMenu } from "@/components/pyramid/PyramidOverlays";
import {
  PILLARS,
  PILLAR_COLOR,
  PILLAR_LABEL,
  type Pillar,
  type Pyramid,
  type PyramidNode,
  type Selection,
  isGreyed,
} from "@/lib/pyramid";

// ── Layout geometry ──────────────────────────────────────────────────────────
// The pyramid reads as three vertical columns (one per locked U1 axis) with the
// converging TAM apex centered above them. Positions are EXPLICIT — ReactFlow's
// auto-layout would squish ~30 industry leaves into an unreadable band, so we
// place every node by hand and only use fitView to center the result once.
const COL_X: Record<Pillar, number> = {
  qualitative: -420,
  quantitative: 0,
  industry: 420,
};
const HEAD_Y = 0; // pillar heads sit on one row
const LEAVES_TOP = 96; // first leaf below its head
const ROW_GAP = 64; // vertical spacing between stacked leaves
const SUBCOL_GAP = 200; // horizontal spacing when a pillar wraps into sub-columns
const APEX_Y = -150; // TAM apex above the heads (converging legs read downward)

// Industry has ~30 concepts. Cap the column to the top-N by weight and surface
// the remainder behind a single "+N more" node so the band never overflows.
const INDUSTRY_CAP = 14;
const INDUSTRY_ROWS_PER_SUBCOL = 7; // wrap long columns into side-by-side stacks

interface PyramidNodeData extends Record<string, unknown> {
  node: PyramidNode;
  selected: boolean;
  greyed: boolean;
  color: string;
}
interface PillarNodeData extends Record<string, unknown> {
  pillar: Pillar;
  color: string;
}
interface ApexNodeData extends Record<string, unknown> {
  label: string;
}
interface MoreNodeData extends Record<string, unknown> {
  count: number;
}
type FlowNode =
  | Node<PyramidNodeData, "pyramid">
  | Node<PillarNodeData, "pillar">
  | Node<ApexNodeData, "apex">
  | Node<MoreNodeData, "more">;

const NODE_TYPES: NodeTypes = {
  pyramid: PyramidLeaf,
  pillar: PillarHead,
  apex: ApexNode,
  more: MoreNode,
};

const DEFAULT_EDGE_OPTIONS = {
  type: "smoothstep" as const,
  style: { stroke: "var(--canvas-line)", strokeWidth: 1.5 },
  animated: false,
};
// Center the explicit layout on first paint; minZoom lets the tall industry
// column zoom out without clipping. We never re-fit on selection.
const FIT_VIEW_OPTIONS = { padding: 0.18 };
const PRO_OPTIONS = { hideAttribution: true };

export function PyramidGraph({
  pyramid,
  selection,
  onSelect,
}: {
  pyramid: Pyramid;
  selection: Selection;
  onSelect: (node: PyramidNode, additive: boolean) => void;
}) {
  const { nodes, edges } = useMemo(() => layout(pyramid, selection), [pyramid, selection]);

  // AC2.2: right-click context menu + 250ms hover-intent ghost card.
  const [menu, setMenu] = useState<MenuAnchor | null>(null);
  const [ghost, setGhost] = useState<MenuAnchor | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHover = useCallback(() => {
    if (hoverTimer.current !== null) {
      clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  }, []);

  const handleNodeClick = useCallback(
    (evt: React.MouseEvent, n: Node) => {
      if (n.type === "pyramid") onSelect((n.data as PyramidNodeData).node, evt.shiftKey);
    },
    [onSelect],
  );

  const handleNodeContextMenu = useCallback(
    (evt: React.MouseEvent, n: Node) => {
      if (n.type !== "pyramid") return;
      evt.preventDefault();
      clearHover();
      setGhost(null);
      setMenu({ node: (n.data as PyramidNodeData).node, x: evt.clientX, y: evt.clientY });
    },
    [clearHover],
  );

  const handleNodeMouseEnter = useCallback(
    (evt: React.MouseEvent, n: Node) => {
      if (n.type !== "pyramid" || menu) return;
      const { clientX, clientY } = evt;
      const node = (n.data as PyramidNodeData).node;
      clearHover();
      // Ghost card only after a 250ms dwell (no flicker on pass-through).
      hoverTimer.current = setTimeout(() => setGhost({ node, x: clientX, y: clientY }), 250);
    },
    [menu, clearHover],
  );

  const handleNodeMouseLeave = useCallback(() => {
    clearHover();
    setGhost(null);
  }, [clearHover]);

  return (
    <div
      className="rounded-[var(--r-4)] h-[640px] overflow-hidden border border-[var(--card-border)]"
      style={{ background: "var(--canvas-bg)" }}
      data-testid="pyramid-canvas"
    >
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
          fitView
          fitViewOptions={FIT_VIEW_OPTIONS}
          proOptions={PRO_OPTIONS}
          onNodeClick={handleNodeClick}
          onNodeContextMenu={handleNodeContextMenu}
          onNodeMouseEnter={handleNodeMouseEnter}
          onNodeMouseLeave={handleNodeMouseLeave}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          minZoom={0.3}
          maxZoom={1.5}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1}
            color="var(--canvas-line)"
          />
          <Controls
            showInteractive={false}
            className="!border-[var(--card-border)] !rounded-[var(--r-2)] !shadow-[var(--card-shadow)] !bg-[var(--bg-1)]"
          />
        </ReactFlow>
      </ReactFlowProvider>

      {ghost && !menu ? <GhostCard anchor={ghost} /> : null}
      {menu ? (
        <NodeContextMenu
          anchor={menu}
          onClose={() => setMenu(null)}
          onAction={(key, node) => {
            // Expand/annotate land with their features; "Suggest framework" and
            // "Expand children" reuse the existing select flow as the entry point.
            if (key === "expand" || key === "framework") onSelect(node, false);
          }}
        />
      ) : null}
    </div>
  );
}

// Build the explicit node + edge sets. Each pillar is a vertical stack under
// its head; the apex links to all three heads (converging legs). Industry caps
// at INDUSTRY_CAP visible leaves and wraps into sub-columns so it never spills.
function layout(pyramid: Pyramid, selection: Selection): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = [];
  const edges: Edge[] = [];

  // Apex TAM node, centered over the three heads.
  nodes.push({
    id: "apex",
    type: "apex",
    position: { x: COL_X.quantitative, y: APEX_Y },
    data: { label: "TAM" },
    draggable: false,
  });

  for (const pillar of PILLARS) {
    const color = PILLAR_COLOR[pillar];
    const baseX = COL_X[pillar];
    const headId = `head:${pillar}`;
    nodes.push({
      id: headId,
      type: "pillar",
      position: { x: baseX, y: HEAD_Y },
      data: { pillar, color },
      draggable: false,
    });
    edges.push({
      id: `e:apex:${headId}`,
      source: "apex",
      target: headId,
      style: { stroke: color, strokeWidth: 1.5, opacity: 0.6 },
    });

    const all = pyramid.nodes.filter((n) => n.pillar === pillar);
    // Industry can hold ~30 concepts — cap to top-N (already weight-sorted) and
    // roll the rest into a single "+N more" node at the bottom of the column.
    const capped = pillar === "industry" && all.length > INDUSTRY_CAP;
    const leaves = capped ? all.slice(0, INDUSTRY_CAP) : all;
    const rowsPerSub = pillar === "industry" ? INDUSTRY_ROWS_PER_SUBCOL : Number.POSITIVE_INFINITY;

    leaves.forEach((leaf, i) => {
      const sub = Math.floor(i / rowsPerSub);
      const row = i % rowsPerSub;
      nodes.push({
        id: leaf.id,
        type: "pyramid",
        position: {
          x: baseX + sub * SUBCOL_GAP,
          y: LEAVES_TOP + row * ROW_GAP,
        },
        data: {
          node: leaf,
          selected: (selection[leaf.pillar] ?? []).includes(leaf.key),
          greyed: isGreyed(pyramid, selection, leaf),
          color,
        },
        draggable: false,
      });
      edges.push({
        id: `e:${headId}:${leaf.id}`,
        source: headId,
        target: leaf.id,
      });
    });

    if (capped) {
      const hiddenCount = all.length - leaves.length;
      const lastRow = (leaves.length - 1) % rowsPerSub;
      const lastSub = Math.floor((leaves.length - 1) / rowsPerSub);
      nodes.push({
        id: `more:${pillar}`,
        type: "more",
        position: {
          x: baseX + lastSub * SUBCOL_GAP,
          y: LEAVES_TOP + (lastRow + 1) * ROW_GAP,
        },
        data: { count: hiddenCount },
        draggable: false,
      });
      edges.push({
        id: `e:${headId}:more`,
        source: headId,
        target: `more:${pillar}`,
      });
    }
  }

  return { nodes, edges };
}

function ApexNode({ data }: NodeProps<ApexNodeData>) {
  return (
    <div
      className="canvas-card px-4 py-2 text-center border-2 border-[var(--accent)]"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "transparent", border: 0 }}
      />
      <div className="display text-[16px] text-[var(--fg-1)] leading-none">{data.label}</div>
      <div className="text-[9px] uppercase tracking-[0.1em] text-[var(--fg-3)] mt-1">Apex</div>
    </div>
  );
}

function PillarHead({ data }: NodeProps<PillarNodeData>) {
  return (
    <div className="text-center" style={{ width: 170 }}>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "transparent", border: 0 }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "transparent", border: 0 }}
      />
      <div className="display text-[18px] leading-none" style={{ color: data.color }}>
        {PILLAR_LABEL[data.pillar]}
      </div>
      <div className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)] mt-1">Pillar</div>
    </div>
  );
}

function PyramidLeaf({ data }: NodeProps<PyramidNodeData>) {
  const { node, selected, greyed, color } = data;
  return (
    <button
      type="button"
      aria-pressed={selected}
      data-greyed={greyed}
      data-pillar={node.pillar}
      title={greyed ? `${node.label} — incompatible with current selection` : node.label}
      className="canvas-card w-[160px] px-3 py-2.5 text-left border-2 transition-opacity"
      style={{
        borderRadius: "var(--r-3)",
        // Axis color on the stroke; selection deepens it with a ring halo.
        borderColor: color,
        boxShadow: selected ? `0 0 0 2px ${color}` : undefined,
        opacity: greyed ? 0.32 : 1,
        cursor: "pointer",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "transparent", border: 0 }}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-[var(--fg-1)] leading-[1.25] line-clamp-2">
          {node.label}
        </span>
        <span className="role-chip shrink-0 tabular-nums">{node.weight}</span>
      </div>
    </button>
  );
}

function MoreNode({ data }: NodeProps<MoreNodeData>) {
  return (
    <div
      className="w-[160px] px-3 py-2 text-center border border-dashed border-[var(--card-border)] text-[11px] text-[var(--fg-3)]"
      style={{ borderRadius: "var(--r-3)", background: "var(--bg-1)" }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "transparent", border: 0 }}
      />
      +{data.count} more
    </div>
  );
}
