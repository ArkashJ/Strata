"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import { useMemo } from "react";

import { type BuildResponse, formatUSD } from "@/lib/api";

type ScenarioInput = BuildResponse["scenarios"][number]["inputs_used"][number];
type Scenario = BuildResponse["scenarios"][number];

interface TargetNodeData extends Record<string, unknown> {
  kind: "target";
  name: string;
  midpoint: number;
}
interface FrameworkNodeData extends Record<string, unknown> {
  kind: "framework";
  scenario: Scenario;
}
interface PrimitiveNodeData extends Record<string, unknown> {
  kind: "primitive";
  input: ScenarioInput;
}
type StrataNode =
  | Node<TargetNodeData, "target">
  | Node<FrameworkNodeData, "framework">
  | Node<PrimitiveNodeData, "primitive">;

const NODE_TYPES: NodeTypes = {
  target: TargetCard,
  framework: FrameworkCard,
  primitive: PrimitiveCard,
};

const DEFAULT_EDGE_OPTIONS = {
  type: "smoothstep" as const,
  style: { stroke: "var(--canvas-line)", strokeWidth: 1.5 },
  animated: false,
};

const FIT_VIEW_OPTIONS = { padding: 0.18 };
const PRO_OPTIONS = { hideAttribution: true };

/**
 * Centerpiece graph — Harvey AI workflow-canvas styling.
 * Target → frameworks → primitives, soft connecting curves on a sage canvas.
 */
export function ScenarioGraph({ build }: { build: BuildResponse }) {
  const { nodes, edges } = useMemo(() => buildGraph(build), [build]);

  return (
    <div
      className="rounded-[var(--r-4)] h-[520px] overflow-hidden border border-[var(--card-border)]"
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
          minZoom={0.4}
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

interface GraphData {
  nodes: StrataNode[];
  edges: Edge[];
}

function buildGraph(build: BuildResponse): GraphData {
  const frameworkCount = build.scenarios.length;
  const frameworkSpacing = 320;
  const frameworkStartX = -((frameworkCount - 1) * frameworkSpacing) / 2;

  const midpoint = (build.triangulated_range.low + build.triangulated_range.high) / 2;

  const nodes: StrataNode[] = [
    {
      id: "target",
      type: "target",
      position: { x: -160, y: 0 },
      data: { kind: "target", name: build.target.concept_name, midpoint },
      draggable: false,
    },
  ];
  const edges: Edge[] = [];

  build.scenarios.forEach((scenario, fIdx) => {
    const fX = frameworkStartX + fIdx * frameworkSpacing;
    const fY = 240;
    const fId = `f-${scenario.framework_slug}`;
    nodes.push({
      id: fId,
      type: "framework",
      position: { x: fX, y: fY },
      data: { kind: "framework", scenario },
      draggable: false,
    });
    edges.push({
      id: `e-target-${fId}`,
      source: "target",
      target: fId,
    });

    const baseInputs = scenario.inputs_used.filter((i) => i.role === "base_value");
    const inputCount = baseInputs.length;
    const inputSpacing = 200;
    const inputStartX = fX - ((inputCount - 1) * inputSpacing) / 2;

    baseInputs.forEach((input, pIdx) => {
      const pId = `p-${fId}-${input.primitive_slug}`;
      const pX = inputStartX + pIdx * inputSpacing;
      const pY = 480;
      nodes.push({
        id: pId,
        type: "primitive",
        position: { x: pX, y: pY },
        data: { kind: "primitive", input },
        draggable: false,
      });
      edges.push({ id: `e-${fId}-${pId}`, source: fId, target: pId });
    });
  });

  return { nodes, edges };
}

function TargetCard({ data }: NodeProps<TargetNodeData>) {
  return (
    <div
      className="canvas-card w-[320px] px-5 py-4 text-left"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <Handle type="source" position={Position.Bottom} style={{ background: "transparent", border: 0 }} />
      <div className="flex items-center gap-2 mb-2">
        <span className="role-chip role-chip--accent">Target TAM</span>
      </div>
      <div className="tam-num text-[28px] text-[var(--fg-1)] leading-[1]">
        {formatUSD(data.midpoint)}
      </div>
      <div className="text-[12px] text-[var(--fg-3)] mt-1.5 truncate">{data.name}</div>
    </div>
  );
}

function FrameworkCard({ data }: NodeProps<FrameworkNodeData>) {
  const { scenario } = data;
  const familyLabel = scenario.method_family.replace(/_/g, " ");
  return (
    <div
      className="canvas-card w-[240px] px-4 py-3 text-left"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "transparent", border: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: "transparent", border: 0 }} />
      <div className="text-[12px] text-[var(--fg-1)] font-medium truncate">
        {scenario.framework_name}
      </div>
      <div className="flex items-center gap-1.5 mt-1.5">
        <span className="role-chip uppercase tracking-[0.04em]">{familyLabel}</span>
      </div>
      <div className="tam-num text-[20px] text-[var(--fg-1)] mt-2.5 tabular-nums">
        {formatUSD(scenario.value)}
      </div>
    </div>
  );
}

function PrimitiveCard({ data }: NodeProps<PrimitiveNodeData>) {
  const { input } = data;
  return (
    <div
      className="canvas-card w-[180px] px-3 py-2.5 text-left"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "transparent", border: 0 }} />
      <div className="text-[11px] text-[var(--fg-2)] leading-[1.3] line-clamp-2">
        {input.primitive_name}
      </div>
      <div className="font-mono text-[12px] text-[var(--fg-1)] mt-1.5 tabular-nums">
        {Intl.NumberFormat("en", {
          notation: "compact",
          maximumFractionDigits: 1,
        }).format(input.value)}{" "}
        <span className="text-[var(--fg-3)]">{input.unit_label}</span>
      </div>
    </div>
  );
}
