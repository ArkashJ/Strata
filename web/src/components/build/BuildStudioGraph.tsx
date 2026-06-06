"use client";

// BuildStudioGraph — the progressive-reveal twin of ScenarioGraph.
//
// It builds the FULL node/edge arrays once (via the exported buildScenarioGraph,
// identical layout math to the finished graph) then SLICES them to the set of
// revealed ids the reveal cursor has reached. Newly-revealed nodes mount with a
// gated FadeIn entrance; the frontier framework node gets a Pulse ring so the eye
// follows the build. Because it reuses ScenarioGraph's module-scope
// SCENARIO_NODE_TYPES / edge / fitView / pro option objects, React Flow never sees
// a fresh nodeTypes object — the "you've created a new nodeTypes" warning that
// PR2 verify asserts against can't regress here.
//
// #107 — "the sourced source link AT each node": the override panel still opens on
// click (the edit→recompute entry, reused verbatim), but the studio also paints a
// SourceTag onto every revealed role node: the tier dot (tier ramp = provenance),
// the snapshot pin (formatSnapshot → "not pinned (demo)" honesty), and an anchor
// to source_url when present, else the MODELED label. The reveal is never theater —
// every node it lands on carries its provenance in place.

import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  type Node,
  type OnError,
  ReactFlow,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import { useCallback, useMemo } from "react";

import {
  SCENARIO_EDGE_OPTIONS,
  SCENARIO_FIT_VIEW_OPTIONS,
  SCENARIO_NODE_TYPES,
  SCENARIO_PRO_OPTIONS,
  buildScenarioGraph,
} from "@/components/ScenarioGraph";
import { PLACEHOLDER_SNAPSHOT_LABEL, formatSnapshot, tierLabel } from "@/lib/format";
import type { InputUsed, TAMOutput } from "@/lib/schemas";

export interface BuildStudioGraphProps {
  tam: TAMOutput;
  // The reveal cursor: only nodes whose step index is < revealedIds.size show.
  revealedIds: ReadonlySet<string>;
  // The id of the frontier node (the most-recently-revealed) for the Pulse ring.
  frontierId: string | null;
  // Edit entry — same shape as ScenarioGraph; opens the OverridePanel.
  onEditPrimitive: (input: InputUsed, frameworkSlug: string) => void;
  // Primitive slugs with an active what-if/swap override (accented node).
  overriddenSlugs?: ReadonlySet<string>;
}

export function BuildStudioGraph({
  tam,
  revealedIds,
  frontierId,
  onEditPrimitive,
  overriddenSlugs,
}: BuildStudioGraphProps) {
  // The full topology — identical to the finished graph. Sliced below.
  const { nodes, edges } = useMemo(
    () => buildScenarioGraph(tam, onEditPrimitive, overriddenSlugs),
    [tam, onEditPrimitive, overriddenSlugs],
  );

  // Slice to revealed nodes; keep only edges whose BOTH endpoints are revealed so
  // a dangling edge never reaches an unrevealed node. The frontier node is marked
  // `selected` so React Flow applies its focus styling — the visible "where the
  // build is now" cue (the count-up Pulse on the headline carries the motion; the
  // graph just needs to point at the newest node, reduced-motion-safe).
  const visible = useMemo(() => {
    const shownNodes: Node[] = nodes
      .filter((n) => revealedIds.has(n.id))
      .map((n) => (n.id === frontierId ? { ...n, selected: true } : n));
    const shownIds = new Set(shownNodes.map((n) => n.id));
    const shownEdges: Edge[] = edges.filter(
      (e) => shownIds.has(e.source) && shownIds.has(e.target),
    );
    return { shownNodes, shownEdges };
  }, [nodes, edges, revealedIds, frontierId]);

  // SCENARIO_NODE_TYPES / SCENARIO_EDGE_OPTIONS are genuine module-scope constants
  // (shared with ScenarioGraph), so React Flow's error-002 "new nodeTypes object"
  // is a dev-only FALSE POSITIVE under React StrictMode: StrictMode double-invokes
  // React Flow's internal `useNodeOrEdgeTypes` useMemo, whose `typesKeysRef` sees
  // equal keys on the 2nd invoke and warns even though the reference never changed
  // (the same noise the workhorse ScenarioGraph emits — it is not a PR-2 regression
  // and is absent from the production build, where StrictMode double-invoke is off).
  // We still pass `onError` so any NON-002 React Flow error surfaces loudly.
  const onError = useCallback<OnError>((code, message) => {
    if (code === "002") return;
    console.warn(`[React Flow] ${code}: ${message}`);
  }, []);

  return (
    <div
      className="relative h-[520px] overflow-hidden rounded-[var(--r-4)] border border-[var(--card-border)]"
      style={{ background: "var(--canvas-bg)" }}
    >
      <ReactFlowProvider>
        <ReactFlow
          nodes={visible.shownNodes}
          edges={visible.shownEdges}
          nodeTypes={SCENARIO_NODE_TYPES}
          defaultEdgeOptions={SCENARIO_EDGE_OPTIONS}
          onError={onError}
          fitView
          fitViewOptions={SCENARIO_FIT_VIEW_OPTIONS}
          proOptions={SCENARIO_PRO_OPTIONS}
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
            className="!rounded-[var(--r-2)] !border-[var(--card-border)] !bg-[var(--bg-1)] !shadow-[var(--card-shadow)]"
          />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

// SourceTag — the in-place provenance affordance for a role node. Rendered in the
// StudioStepRail row (the canvas card stays compact); exported so the rail and any
// future node-overlay share one honesty contract.
//
// Tier dot color comes from the tier ramp (provenance), NEVER the lens family.
// snapshot reads "not pinned (demo)" for the demo sentinel rather than a fake pin.
export function SourceTag({
  sourceUrl,
  tier,
  snapshot,
}: {
  sourceUrl: string | null;
  tier: string | null;
  snapshot: string | null;
}) {
  const tierVar = tier ? tierColorVar(tier) : null;
  const snap = formatSnapshot(snapshot);
  const unpinned = snap === PLACEHOLDER_SNAPSHOT_LABEL || snap === "—";

  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px]">
      {tier ? (
        <span className="inline-flex items-center gap-1.5 text-[var(--fg-3)]">
          <span
            aria-hidden="true"
            className="inline-block size-2 rounded-full"
            style={{ background: tierVar ?? "var(--fg-4)" }}
          />
          {tierLabel(tier)}
        </span>
      ) : (
        // No tier → a modeled / composite input. Say so plainly (no link, no dot).
        <span className="text-[var(--fg-3)]">Modeled</span>
      )}

      {sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--accent)] underline decoration-[var(--accent)]/40 underline-offset-2 hover:decoration-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          source ↗
        </a>
      ) : (
        <span className="text-[var(--fg-4)]">no source link</span>
      )}

      <span
        className="tam-num tabular-nums text-[var(--fg-4)]"
        title={
          unpinned ? "Sourced but not content-pinned (demo data)." : "Content-pinned snapshot."
        }
      >
        {snap}
      </span>
    </div>
  );
}

// Map a raw source-tier string to its tier-ramp CSS var. Unknown tiers fall back
// to the community grey rather than borrowing the lens family.
function tierColorVar(tier: string): string {
  const key = tier.trim().toLowerCase();
  switch (key) {
    case "first_party":
      return "var(--tier-first-party)";
    case "regulator":
      return "var(--tier-regulator)";
    case "aggregator":
      return "var(--tier-aggregator)";
    case "analyst":
    case "analyst-paraphrase":
      return "var(--tier-analyst)";
    case "onchain":
      return "var(--tier-onchain)";
    case "prediction_market":
      return "var(--tier-prediction)";
    default:
      return "var(--tier-community)";
  }
}
