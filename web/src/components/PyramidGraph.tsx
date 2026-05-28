"use client";

import { useCallback, useMemo } from "react";
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

import {
  PILLAR_LABEL,
  type Pillar,
  type Pyramid,
  type PyramidNode,
  type Selection,
  isGreyed,
} from "@/lib/pyramid";

// Triangle apex per pillar — the three locked U1 axes laid out as a pyramid:
// Qualitative top-left, Quantitative top-right, Industry bottom-centre.
const PILLAR_ANCHOR: Record<Pillar, { x: number; y: number; dx: number; dy: number }> = {
  qualitative: { x: -360, y: 40, dx: 0, dy: 96 },
  quantitative: { x: 360, y: 40, dx: 0, dy: 96 },
  industry: { x: 0, y: 460, dx: 250, dy: 0 },
};

interface PyramidNodeData extends Record<string, unknown> {
  node: PyramidNode;
  selected: boolean;
  greyed: boolean;
}
interface PillarNodeData extends Record<string, unknown> {
  pillar: Pillar;
}
type FlowNode = Node<PyramidNodeData, "pyramid"> | Node<PillarNodeData, "pillar">;

const NODE_TYPES: NodeTypes = {
  pyramid: PyramidLeaf,
  pillar: PillarHead,
};

const DEFAULT_EDGE_OPTIONS = {
  type: "smoothstep" as const,
  style: { stroke: "var(--canvas-line)", strokeWidth: 1.5 },
  animated: false,
};
const FIT_VIEW_OPTIONS = { padding: 0.2 };
const PRO_OPTIONS = { hideAttribution: true };

export function PyramidGraph({
  pyramid,
  selection,
  onSelect,
}: {
  pyramid: Pyramid;
  selection: Selection;
  onSelect: (node: PyramidNode) => void;
}) {
  const { nodes, edges } = useMemo(() => layout(pyramid, selection), [pyramid, selection]);

  const handleNodeClick = useCallback(
    (_evt: React.MouseEvent, n: Node) => {
      if (n.type === "pyramid") onSelect((n.data as PyramidNodeData).node);
    },
    [onSelect],
  );

  return (
    <div
      className="rounded-[var(--r-4)] h-[600px] overflow-hidden border border-[var(--card-border)]"
      style={{ background: "var(--canvas-bg)" }}
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
    </div>
  );
}

function layout(pyramid: Pyramid, selection: Selection): { nodes: FlowNode[]; edges: Edge[] } {
  const nodes: FlowNode[] = [];
  const edges: Edge[] = [];

  for (const pillar of Object.keys(PILLAR_ANCHOR) as Pillar[]) {
    const anchor = PILLAR_ANCHOR[pillar];
    const headId = `head:${pillar}`;
    nodes.push({
      id: headId,
      type: "pillar",
      position: { x: anchor.x, y: pillar === "industry" ? anchor.y - 110 : anchor.y - 70 },
      data: { pillar },
      draggable: false,
    });

    const leaves = pyramid.nodes.filter((n) => n.pillar === pillar);
    const startX = anchor.dx ? anchor.x - ((leaves.length - 1) * anchor.dx) / 2 : anchor.x;

    leaves.forEach((leaf, i) => {
      nodes.push({
        id: leaf.id,
        type: "pyramid",
        position: {
          x: startX + i * anchor.dx,
          y: anchor.y + i * anchor.dy,
        },
        data: {
          node: leaf,
          selected: selection[leaf.pillar] === leaf.key,
          greyed: isGreyed(pyramid, selection, leaf),
        },
        draggable: false,
      });
      edges.push({
        id: `e:${headId}:${leaf.id}`,
        source: headId,
        target: leaf.id,
      });
    });
  }

  return { nodes, edges };
}

function PillarHead({ data }: NodeProps<PillarNodeData>) {
  return (
    <div className="text-center" style={{ width: 200 }}>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "transparent", border: 0 }}
      />
      <div className="display text-[18px] text-[var(--fg-1)] leading-none">
        {PILLAR_LABEL[data.pillar]}
      </div>
      <div className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)] mt-1">Pillar</div>
    </div>
  );
}

function PyramidLeaf({ data }: NodeProps<PyramidNodeData>) {
  const { node, selected, greyed } = data;
  const ring = selected
    ? "border-[var(--accent)] shadow-[0_0_0_2px_var(--accent-ring)]"
    : "border-[var(--card-border)]";
  return (
    <button
      type="button"
      aria-pressed={selected}
      data-greyed={greyed}
      title={greyed ? `${node.label} — incompatible with current selection` : node.label}
      className={`canvas-card w-[170px] px-3 py-2.5 text-left border ${ring} transition-opacity`}
      style={{ borderRadius: "var(--r-3)", opacity: greyed ? 0.32 : 1, cursor: "pointer" }}
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
