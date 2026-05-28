"use client";

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
import { useMemo } from "react";

import { lensLabel } from "@/lib/format";
import type { ConceptSummary, FrameworkSummary } from "@/lib/schemas";

/**
 * Read-only pyramid: three axes (Qualitative · Quantitative · Industry).
 *
 *   Qualitative  = analysis lens   (cost_efficiency, latent_demand, ...)
 *   Quantitative = method family   (top_down_spend, bottoms_up_seats, ...)
 *   Industry     = concept         (each curated market identity)
 *
 * The three axes hang off an apex. Clicking a leaf adds a constraint on that
 * axis and greys incompatible siblings (a framework/concept that does not
 * match every active axis constraint dims out). Selection is owned by the
 * page; this component is a pure renderer.
 */

export type Axis = "qualitative" | "quantitative" | "industry";

export interface Selection {
  qualitative: string | null; // lens value
  quantitative: string | null; // method_family value
  industry: string | null; // concept slug
}

const AXIS_LABEL: Record<Axis, string> = {
  qualitative: "Qualitative",
  quantitative: "Quantitative",
  industry: "Industry",
};

const AXIS_TOKEN: Record<Axis, string> = {
  qualitative: "var(--axis-qualitative)",
  quantitative: "var(--axis-quantitative)",
  industry: "var(--axis-industry)",
};

const NODE_TYPES: NodeTypes = {
  apex: ApexCard,
  axis: AxisCard,
  leaf: LeafCard,
};

const DEFAULT_EDGE_OPTIONS = {
  type: "smoothstep" as const,
  style: { stroke: "var(--canvas-line)", strokeWidth: 1.5 },
  animated: false,
};

const FIT_VIEW_OPTIONS = { padding: 0.16 };
const PRO_OPTIONS = { hideAttribution: true };

interface ApexData extends Record<string, unknown> {
  kind: "apex";
}
interface AxisData extends Record<string, unknown> {
  kind: "axis";
  axis: Axis;
  count: number;
}
interface LeafData extends Record<string, unknown> {
  kind: "leaf";
  axis: Axis;
  value: string;
  label: string;
  sublabel: string;
  selected: boolean;
  dimmed: boolean;
  onSelect: (axis: Axis, value: string) => void;
}
type PyramidNode = Node<ApexData, "apex"> | Node<AxisData, "axis"> | Node<LeafData, "leaf">;

interface AxisColumn {
  axis: Axis;
  leaves: { value: string; label: string; sublabel: string }[];
}

export interface PyramidGraphProps {
  concepts: ConceptSummary[];
  frameworks: FrameworkSummary[];
  selection: Selection;
  /** Slugs of concepts allowed by the active geo/time chips. null = no geo/time filter. */
  industryAllow: Set<string> | null;
  onSelect: (axis: Axis, value: string) => void;
}

export function PyramidGraph({
  concepts,
  frameworks,
  selection,
  industryAllow,
  onSelect,
}: PyramidGraphProps) {
  const { nodes, edges } = useMemo(
    () =>
      buildPyramid({
        concepts,
        frameworks,
        selection,
        industryAllow,
        onSelect,
      }),
    [concepts, frameworks, selection, industryAllow, onSelect],
  );

  return (
    <div
      className="rounded-[var(--r-4)] h-full min-h-[520px] overflow-hidden border border-[var(--card-border)]"
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

function uniqueLeaves(
  values: { value: string; label: string; sublabel: string }[],
): { value: string; label: string; sublabel: string }[] {
  const seen = new Map<string, { value: string; label: string; sublabel: string }>();
  for (const v of values) {
    if (!seen.has(v.value)) seen.set(v.value, v);
  }
  return [...seen.values()];
}

/**
 * A framework is compatible with the current selection if it matches every
 * active axis constraint. Concept selection (industry) does not constrain
 * frameworks directly (frameworks are not concept-scoped at v0.2), but lens
 * and method_family do.
 */
function frameworkMatches(f: FrameworkSummary, selection: Selection): boolean {
  if (selection.qualitative && f.lens !== selection.qualitative) return false;
  if (selection.quantitative && f.method_family !== selection.quantitative) return false;
  return true;
}

function leafDimmed(
  axis: Axis,
  value: string,
  selection: Selection,
  frameworks: FrameworkSummary[],
  industryAllow: Set<string> | null,
): boolean {
  if (axis === "industry") {
    // Greyed if a geo/time chip excludes it, or the active lens has no concept
    // on this slug. Industry leaves are concepts; lens narrows them.
    if (industryAllow && !industryAllow.has(value)) return true;
    return false;
  }

  // qualitative (lens) or quantitative (method_family): grey if, given the
  // OTHER active axis constraint, no framework would survive picking this leaf.
  const trial: Selection = { ...selection, [axis]: value };
  return !frameworks.some((f) => frameworkMatches(f, trial));
}

function buildPyramid({
  concepts,
  frameworks,
  selection,
  industryAllow,
  onSelect,
}: {
  concepts: ConceptSummary[];
  frameworks: FrameworkSummary[];
  selection: Selection;
  industryAllow: Set<string> | null;
  onSelect: (axis: Axis, value: string) => void;
}): { nodes: PyramidNode[]; edges: Edge[] } {
  const qualitative = uniqueLeaves(
    frameworks.map((f) => ({
      value: f.lens,
      label: lensLabel(f.lens),
      sublabel: "lens",
    })),
  );
  const quantitative = uniqueLeaves(
    frameworks.map((f) => ({
      value: f.method_family,
      label: lensLabel(f.method_family),
      sublabel: "method",
    })),
  );
  const industry = uniqueLeaves(
    concepts.map((c) => ({
      value: c.slug,
      label: c.name,
      sublabel: lensLabel(c.primary_lens),
    })),
  );

  const columns: AxisColumn[] = [
    { axis: "qualitative", leaves: qualitative },
    { axis: "quantitative", leaves: quantitative },
    { axis: "industry", leaves: industry },
  ];

  const nodes: PyramidNode[] = [];
  const edges: Edge[] = [];

  // Apex centered above the three axis columns.
  const colSpacing = 380;
  const colStartX = -colSpacing;
  const apexX = 0;

  nodes.push({
    id: "apex",
    type: "apex",
    position: { x: apexX - 90, y: 0 },
    data: { kind: "apex" },
    draggable: false,
  });

  columns.forEach((col, cIdx) => {
    const colX = colStartX + cIdx * colSpacing;
    const axisId = `axis-${col.axis}`;
    const axisY = 200;
    nodes.push({
      id: axisId,
      type: "axis",
      position: { x: colX - 110, y: axisY },
      data: { kind: "axis", axis: col.axis, count: col.leaves.length },
      draggable: false,
    });
    edges.push({
      id: `e-apex-${axisId}`,
      source: "apex",
      target: axisId,
      style: { stroke: AXIS_TOKEN[col.axis], strokeWidth: 1.75 },
    });

    const leafSpacing = 84;
    col.leaves.forEach((leaf, lIdx) => {
      const leafId = `leaf-${col.axis}-${leaf.value}`;
      const leafY = axisY + 150 + lIdx * leafSpacing;
      const selected = selection[col.axis] === leaf.value;
      const dimmed =
        !selected && leafDimmed(col.axis, leaf.value, selection, frameworks, industryAllow);
      nodes.push({
        id: leafId,
        type: "leaf",
        position: { x: colX - 130, y: leafY },
        data: {
          kind: "leaf",
          axis: col.axis,
          value: leaf.value,
          label: leaf.label,
          sublabel: leaf.sublabel,
          selected,
          dimmed,
          onSelect,
        },
        draggable: false,
      });
      edges.push({
        id: `e-${axisId}-${leafId}`,
        source: axisId,
        target: leafId,
        style: {
          stroke: dimmed ? "var(--canvas-line)" : AXIS_TOKEN[col.axis],
          strokeWidth: selected ? 2 : 1.25,
          opacity: dimmed ? 0.4 : 1,
        },
      });
    });
  });

  return { nodes, edges };
}

function ApexCard() {
  return (
    <div
      className="canvas-card w-[180px] px-4 py-3 text-center"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "transparent", border: 0 }}
      />
      <span className="role-chip role-chip--accent">Market</span>
      <div className="display text-[18px] text-[var(--fg-1)] mt-1.5 leading-[1.1]">Pyramid</div>
      <div className="text-[11px] text-[var(--fg-3)] mt-1">three axes narrow the space</div>
    </div>
  );
}

function AxisCard({ data }: NodeProps<AxisData>) {
  const color = AXIS_TOKEN[data.axis];
  return (
    <div
      className="canvas-card w-[220px] px-4 py-3 text-left"
      style={{ borderRadius: "var(--r-3)", borderTop: `3px solid ${color}` }}
    >
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
      <div className="text-[13px] font-medium text-[var(--fg-1)]" style={{ color }}>
        {AXIS_LABEL[data.axis]}
      </div>
      <div className="text-[11px] text-[var(--fg-3)] mt-0.5">{data.count} options</div>
    </div>
  );
}

function LeafCard({ data }: NodeProps<LeafData>) {
  const color = AXIS_TOKEN[data.axis];
  return (
    <button
      type="button"
      onClick={() => data.onSelect(data.axis, data.value)}
      aria-pressed={data.selected}
      className="canvas-card w-[260px] px-3 py-2.5 text-left transition-opacity"
      style={{
        borderRadius: "var(--r-3)",
        opacity: data.dimmed ? 0.32 : 1,
        boxShadow: data.selected ? `0 0 0 2px ${color}` : undefined,
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "transparent", border: 0 }}
      />
      <div className="text-[12px] text-[var(--fg-1)] leading-[1.3] line-clamp-2">{data.label}</div>
      <div className="flex items-center gap-1.5 mt-1">
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: color }}
          aria-hidden="true"
        />
        <span className="text-[10px] text-[var(--fg-3)] uppercase tracking-[0.04em]">
          {data.sublabel}
        </span>
        {data.selected && <span className="role-chip role-chip--accent ml-auto">selected</span>}
      </div>
    </button>
  );
}
