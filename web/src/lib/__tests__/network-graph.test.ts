import { describe, expect, it } from "vitest";

import {
  type NetworkGraph,
  buildNetworkGraph,
  collapseBranch,
  detectPatterns,
  mergeSubGraph,
  nodeId,
} from "../network-graph";
import type { ConceptSummary, FrameworkSummary, PrimitiveSummary } from "../schemas";

const concepts: ConceptSummary[] = [
  {
    slug: "doc-gen-pc",
    name: "P&C doc-gen",
    definition: "",
    primary_lens: "cost_efficiency",
    measurement_count: 2,
  },
  {
    slug: "claims-triage",
    name: "Claims triage",
    definition: "",
    // Same lens as the root → same-lens sibling edge.
    primary_lens: "cost_efficiency",
    measurement_count: 1,
  },
  {
    slug: "ai-marketplace",
    name: "AI agents marketplace",
    definition: "",
    primary_lens: "platform_throughput",
    measurement_count: 1,
  },
];

const primitives: PrimitiveSummary[] = [
  {
    slug: "pc-adjuster-count",
    name: "P&C adjuster headcount",
    kind: "atomic_primitive",
    concept_slug: "doc-gen-pc",
    value: 50000,
    unit_label: "people",
  },
  {
    slug: "adjuster-wage",
    name: "Adjuster fully-loaded wage",
    kind: "atomic_primitive",
    // Belongs to the sibling concept but is also a root measurement (cross-use)
    // → drives the shared-measurement edge once folded in via rootDetail.
    concept_slug: "claims-triage",
    value: 90000,
    unit_label: "USD/year",
  },
  {
    slug: "marketplace-gmv",
    name: "Marketplace GMV",
    kind: "composite_primitive",
    concept_slug: "ai-marketplace",
    value: 1.2e9,
    unit_label: "USD",
  },
];

const frameworks: FrameworkSummary[] = [
  {
    slug: "bottoms-up-seats",
    name: "Bottoms-up by seat",
    method_family: "bottoms_up_seats",
    lens: "cost_efficiency",
    input_count: 3,
  },
  {
    slug: "persona-cost",
    name: "Persona × cost",
    method_family: "bottoms_up_seats",
    lens: "cost_efficiency",
    input_count: 2,
  },
  {
    slug: "take-rate",
    name: "Volume × take rate",
    method_family: "top_down_spend",
    lens: "platform_throughput",
    input_count: 2,
  },
];

describe("buildNetworkGraph", () => {
  it("roots at the concept and is deterministic (sorted)", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
    });
    const root = g.nodes.find((n) => n.id === nodeId("concept", "doc-gen-pc"));
    expect(root).toBeDefined();
    expect(root?.depth).toBe(0);

    const ids = g.nodes.map((n) => n.id);
    expect([...ids].sort()).toEqual(ids);
  });

  it("links primitives that measure the root concept", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
    });
    expect(g.nodes.some((n) => n.id === nodeId("primitive", "pc-adjuster-count"))).toBe(true);
    const edge = g.edges.find(
      (e) =>
        e.from === nodeId("concept", "doc-gen-pc") &&
        e.to === nodeId("primitive", "pc-adjuster-count"),
    );
    expect(edge?.signals[0]?.type).toBe("measures");
  });

  it("links sibling concepts that share the primary lens", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
    });
    const edge = g.edges.find(
      (e) =>
        e.from === nodeId("concept", "doc-gen-pc") && e.to === nodeId("concept", "claims-triage"),
    );
    expect(edge).toBeDefined();
    expect(edge?.signals.some((s) => s.type === "primary_lens")).toBe(true);
  });

  it("links frameworks matching the root lens and ties same-method-family pairs", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
    });
    expect(g.nodes.some((n) => n.id === nodeId("framework", "bottoms-up-seats"))).toBe(true);
    expect(g.nodes.some((n) => n.id === nodeId("framework", "persona-cost"))).toBe(true);
    // The two cost_efficiency / bottoms_up_seats frameworks share a method family.
    const fwEdge = g.edges.find(
      (e) =>
        e.from === nodeId("framework", "bottoms-up-seats") &&
        e.to === nodeId("framework", "persona-cost"),
    );
    expect(fwEdge?.signals[0]?.type).toBe("method_family");
    // A different-lens framework is not reachable from this root.
    expect(g.nodes.some((n) => n.id === nodeId("framework", "take-rate"))).toBe(false);
  });

  it("folds root.measurements[] into shared-measurement detection", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
      // adjuster-wage belongs to claims-triage but is a measurement of the root.
      rootDetail: { measurements: ["pc-adjuster-count", "adjuster-wage"] },
    });
    const sib = g.edges.find(
      (e) =>
        e.from === nodeId("concept", "doc-gen-pc") && e.to === nodeId("concept", "claims-triage"),
    );
    expect(sib?.signals.some((s) => s.type === "shared_measurement")).toBe(true);
  });

  it("returns a lone root node for an unknown slug", () => {
    const g = buildNetworkGraph({
      rootSlug: "nope",
      concepts,
      primitives,
      frameworks,
    });
    expect(g.nodes).toHaveLength(1);
    expect(g.edges).toHaveLength(0);
    expect(g.nodes[0]?.depth).toBe(0);
  });
});

describe("detectPatterns", () => {
  it("flags edges sharing a signal value across the threshold", () => {
    const g = buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
      // Fold a second primitive in via measurements so two edges carry the
      // same `measures::doc-gen-pc` value and clustering math has something
      // to group at threshold 2.
      rootDetail: { measurements: ["pc-adjuster-count", "adjuster-wage"] },
    });
    const clusters = detectPatterns(g.edges, 2);
    const measuresCluster = [...clusters.keys()].find((k) => k.startsWith("measures::"));
    expect(measuresCluster).toBeDefined();
  });

  it("ignores signals without a shared value", () => {
    const clusters = detectPatterns(
      [
        {
          id: "a__b",
          from: "a",
          to: "b",
          signals: [{ type: "measures", label: "x" }],
        },
        {
          id: "a__c",
          from: "a",
          to: "c",
          signals: [{ type: "measures", label: "x" }],
        },
      ],
      2,
    );
    expect(clusters.size).toBe(0);
  });
});

describe("mergeSubGraph + collapseBranch (multi-hop walk)", () => {
  function rootGraph(): NetworkGraph {
    return buildNetworkGraph({
      rootSlug: "doc-gen-pc",
      concepts,
      primitives,
      frameworks,
    });
  }

  it("merges an expansion under the expanded parent and stamps depth/addedBy", () => {
    const base = rootGraph();
    const parentId = nodeId("concept", "claims-triage");
    const sub = buildNetworkGraph({
      rootSlug: "claims-triage",
      concepts,
      primitives,
      frameworks,
    });
    const { graph, addedNodeIds } = mergeSubGraph(base, sub, parentId, 1);
    // claims-triage owns adjuster-wage → that primitive should arrive at depth 2.
    const wage = graph.nodes.find((n) => n.id === nodeId("primitive", "adjuster-wage"));
    expect(wage).toBeDefined();
    expect(wage?.depth).toBe(2);
    expect(wage?.addedBy).toBe(parentId);
    expect(addedNodeIds).toContain(nodeId("primitive", "adjuster-wage"));
  });

  it("re-roots sub-graph edges by depth-0 root, not by sorted-first node", () => {
    // A hand-built sub-graph whose root ("z-root") sorts AFTER its child
    // ("a-child"): a naive sub.nodes[0] re-root would wrongly remap the child's
    // edges. mergeSubGraph must key off the depth-0 node instead.
    const base: NetworkGraph = {
      nodes: [
        {
          id: "parent",
          kind: "concept",
          slug: "parent",
          label: "Parent",
          depth: 0,
        },
      ],
      edges: [],
    };
    const sub: NetworkGraph = {
      nodes: [
        {
          id: "a-child",
          kind: "primitive",
          slug: "a-child",
          label: "A",
          depth: 1,
        },
        { id: "z-root", kind: "concept", slug: "z-root", label: "Z", depth: 0 },
      ],
      edges: [{ id: "a-child__z-root", from: "z-root", to: "a-child", signals: [] }],
    };
    const { graph } = mergeSubGraph(base, sub, "parent", 0);
    // The edge from the sub-root is re-rooted onto the live parent.
    expect(graph.edges.some((e) => e.from === "parent" && e.to === "a-child")).toBe(true);
    // The sub-root is dropped (it's the same logical node as the parent).
    expect(graph.nodes.some((n) => n.id === "z-root")).toBe(false);
  });

  it("collapse removes only what the expanded branch introduced, never the root", () => {
    const base = rootGraph();
    const parentId = nodeId("concept", "claims-triage");
    const sub = buildNetworkGraph({
      rootSlug: "claims-triage",
      concepts,
      primitives,
      frameworks,
    });
    const merged = mergeSubGraph(base, sub, parentId, 1).graph;
    const { graph, removedNodeIds } = collapseBranch(merged, parentId);
    expect(removedNodeIds).toContain(nodeId("primitive", "adjuster-wage"));
    // Root survives, and so does the sibling concept itself (only its children go).
    expect(graph.nodes.some((n) => n.id === nodeId("concept", "doc-gen-pc"))).toBe(true);
    expect(graph.nodes.some((n) => n.id === nodeId("primitive", "adjuster-wage"))).toBe(false);
  });
});
