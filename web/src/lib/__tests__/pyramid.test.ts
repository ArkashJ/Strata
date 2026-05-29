import { describe, expect, it } from "vitest";

import {
  PILLARS,
  type Pyramid,
  type PyramidNode,
  buildPyramid,
  compatibleFrameworks,
  isGreyed,
  narrow,
} from "../pyramid";
import type { ConceptSummary, FrameworkSummary, PrimitiveSummary } from "../schemas";

function nodeById(p: Pyramid, id: string): PyramidNode {
  const found = p.nodes.find((n) => n.id === id);
  if (!found) throw new Error(`node ${id} missing`);
  return found;
}

const concepts: ConceptSummary[] = [
  {
    slug: "us-pc-doc-gen",
    name: "P&C doc-gen, US",
    definition: "",
    primary_lens: "cost_efficiency",
    measurement_count: 3,
  },
  {
    slug: "ai-agents-marketplace",
    name: "AI agents marketplace",
    definition: "",
    primary_lens: "platform_throughput",
    measurement_count: 2,
  },
];

const frameworks: FrameworkSummary[] = [
  {
    slug: "bottoms-up-seats",
    name: "Bottoms-up by seat",
    method_family: "bottoms_up_seats",
    lens: "cost_efficiency",
    input_count: 4,
  },
  {
    slug: "top-down-spend",
    name: "Top-down from spend",
    method_family: "top_down_spend",
    lens: "cost_efficiency",
    input_count: 2,
  },
  {
    slug: "marketplace-throughput",
    name: "Marketplace take-rate",
    method_family: "value_chain",
    lens: "platform_throughput",
    input_count: 2,
  },
];

const primitives: PrimitiveSummary[] = [
  {
    slug: "n-carriers",
    name: "# carriers",
    kind: "atomic",
    concept_slug: "us-pc-doc-gen",
    value: 2800,
    unit_label: "carriers",
  },
  {
    slug: "acv-seat",
    name: "ACV / seat",
    kind: "atomic",
    concept_slug: "us-pc-doc-gen",
    value: 480,
    unit_label: "$/seat",
  },
  {
    slug: "gmv-agents",
    name: "Agent GMV",
    kind: "atomic",
    concept_slug: "ai-agents-marketplace",
    value: 1_000_000,
    unit_label: "$",
  },
];

function fixture(): Pyramid {
  return buildPyramid(concepts, frameworks, primitives);
}

describe("buildPyramid topology", () => {
  it("emits exactly the three locked pillars", () => {
    const p = fixture();
    const pillars = new Set(p.nodes.map((n) => n.pillar));
    expect([...pillars].sort()).toEqual([...PILLARS].sort());
  });

  it("derives qualitative nodes from lenses with framework counts as weight", () => {
    const p = fixture();
    const qual = p.nodes.filter((n) => n.pillar === "qualitative");
    const cost = qual.find((n) => n.key === "cost_efficiency");
    expect(cost).toBeDefined();
    expect(cost?.weight).toBe(2); // two frameworks carry cost_efficiency
    expect(cost?.label).toBe("Cost Efficiency");
  });

  it("derives quantitative nodes from method families", () => {
    const p = fixture();
    const quant = p.nodes.filter((n) => n.pillar === "quantitative").map((n) => n.key);
    expect(quant).toContain("bottoms_up_seats");
    expect(quant).toContain("top_down_spend");
    expect(quant).toContain("value_chain");
  });

  it("derives one industry node per concept, weighted by primitive count", () => {
    const p = fixture();
    const ind = p.nodes.filter((n) => n.pillar === "industry");
    expect(ind).toHaveLength(2);
    const doc = ind.find((n) => n.key === "us-pc-doc-gen");
    expect(doc?.weight).toBe(2); // two primitives reference this concept
    expect(doc?.label).toBe("P&C doc-gen, US");
  });

  it("sorts nodes deterministically (weight desc, then key)", () => {
    const p = fixture();
    const quant = p.nodes.filter((n) => n.pillar === "quantitative");
    // all weight 1 → tie broken by key ascending
    expect(quant.map((n) => n.key)).toEqual(["bottoms_up_seats", "top_down_spend", "value_chain"]);
  });

  it("does not throw and yields empty pillars for empty inputs", () => {
    const p = buildPyramid([], [], []);
    expect(p.nodes).toEqual([]);
    expect(compatibleFrameworks(p, {})).toEqual([]);
  });
});

describe("compatibleFrameworks", () => {
  it("returns every framework with no selection", () => {
    const p = fixture();
    expect(compatibleFrameworks(p, {})).toHaveLength(3);
  });

  it("narrows by selected lens", () => {
    const p = fixture();
    const out = compatibleFrameworks(p, { qualitative: ["cost_efficiency"] });
    expect(out.map((f) => f.slug).sort()).toEqual(["bottoms-up-seats", "top-down-spend"]);
  });

  it("narrows by selected method family", () => {
    const p = fixture();
    const out = compatibleFrameworks(p, { quantitative: ["value_chain"] });
    expect(out.map((f) => f.slug)).toEqual(["marketplace-throughput"]);
  });

  it("narrows by selected industry via its primary lens", () => {
    const p = fixture();
    const out = compatibleFrameworks(p, {
      industry: ["ai-agents-marketplace"],
    });
    expect(out.map((f) => f.slug)).toEqual(["marketplace-throughput"]);
  });

  it("intersects multiple selections", () => {
    const p = fixture();
    const out = compatibleFrameworks(p, {
      qualitative: ["cost_efficiency"],
      quantitative: ["top_down_spend"],
    });
    expect(out.map((f) => f.slug)).toEqual(["top-down-spend"]);
  });

  it("yields no frameworks for a contradictory selection", () => {
    const p = fixture();
    const out = compatibleFrameworks(p, {
      qualitative: ["platform_throughput"],
      quantitative: ["bottoms_up_seats"],
    });
    expect(out).toEqual([]);
  });

  it("ORs keys within a pillar (shift-click union)", () => {
    const p = fixture();
    // Both lenses selected → every framework on either lens survives.
    const out = compatibleFrameworks(p, {
      qualitative: ["cost_efficiency", "platform_throughput"],
    });
    expect(out.map((f) => f.slug).sort()).toEqual([
      "bottoms-up-seats",
      "marketplace-throughput",
      "top-down-spend",
    ]);
  });

  it("treats an empty pillar array as no constraint", () => {
    const p = fixture();
    expect(compatibleFrameworks(p, { qualitative: [] })).toHaveLength(3);
  });
});

describe("isGreyed", () => {
  it("greys un-selected siblings within the same pillar", () => {
    const p = fixture();
    const sel = { qualitative: ["cost_efficiency"] };
    expect(isGreyed(p, sel, nodeById(p, "qualitative:platform_throughput"))).toBe(true);
    expect(isGreyed(p, sel, nodeById(p, "qualitative:cost_efficiency"))).toBe(false);
  });

  it("keeps every OR'd sibling active within the same pillar", () => {
    const p = fixture();
    const sel = { qualitative: ["cost_efficiency", "platform_throughput"] };
    expect(isGreyed(p, sel, nodeById(p, "qualitative:cost_efficiency"))).toBe(false);
    expect(isGreyed(p, sel, nodeById(p, "qualitative:platform_throughput"))).toBe(false);
  });

  it("greys cross-pillar nodes that lose all reachable frameworks", () => {
    const p = fixture();
    const sel = { qualitative: ["cost_efficiency"] };
    // value_chain only appears on a platform_throughput framework → greyed
    expect(isGreyed(p, sel, nodeById(p, "quantitative:value_chain"))).toBe(true);
    expect(isGreyed(p, sel, nodeById(p, "quantitative:bottoms_up_seats"))).toBe(false);
  });

  it("ungreys a cross-pillar node once its lens is OR'd in", () => {
    const p = fixture();
    const sel = { qualitative: ["cost_efficiency", "platform_throughput"] };
    // value_chain's framework lens is now selected → reachable.
    expect(isGreyed(p, sel, nodeById(p, "quantitative:value_chain"))).toBe(false);
  });

  it("greys industry nodes whose primary lens conflicts with a selected lens", () => {
    const p = fixture();
    const sel = { qualitative: ["cost_efficiency"] };
    expect(isGreyed(p, sel, nodeById(p, "industry:ai-agents-marketplace"))).toBe(true);
    expect(isGreyed(p, sel, nodeById(p, "industry:us-pc-doc-gen"))).toBe(false);
  });

  it("greys nothing when there is no selection", () => {
    const p = fixture();
    for (const n of p.nodes) {
      expect(isGreyed(p, {}, n)).toBe(false);
    }
  });
});

describe("narrow (plain click)", () => {
  it("sets the selection for a pillar", () => {
    const p = fixture();
    expect(narrow({}, nodeById(p, "qualitative:cost_efficiency"))).toEqual({
      qualitative: ["cost_efficiency"],
    });
  });

  it("replaces a prior choice in the same pillar", () => {
    const p = fixture();
    const platform = nodeById(p, "qualitative:platform_throughput");
    expect(narrow({ qualitative: ["cost_efficiency"] }, platform)).toEqual({
      qualitative: ["platform_throughput"],
    });
  });

  it("collapses a multi-select pillar to a single choice", () => {
    const p = fixture();
    const platform = nodeById(p, "qualitative:platform_throughput");
    expect(narrow({ qualitative: ["cost_efficiency", "platform_throughput"] }, platform)).toEqual({
      qualitative: ["platform_throughput"],
    });
  });

  it("clears the pillar when re-clicking the sole active node", () => {
    const p = fixture();
    const node = nodeById(p, "qualitative:cost_efficiency");
    expect(narrow({ qualitative: ["cost_efficiency"] }, node)).toEqual({});
  });

  it("keeps selections in other pillars intact", () => {
    const p = fixture();
    const mf = nodeById(p, "quantitative:top_down_spend");
    expect(narrow({ qualitative: ["cost_efficiency"] }, mf)).toEqual({
      qualitative: ["cost_efficiency"],
      quantitative: ["top_down_spend"],
    });
  });
});

describe("narrow (shift-click / additive)", () => {
  it("ORs a second key into the pillar", () => {
    const p = fixture();
    const platform = nodeById(p, "qualitative:platform_throughput");
    expect(
      narrow({ qualitative: ["cost_efficiency"] }, platform, {
        additive: true,
      }),
    ).toEqual({ qualitative: ["cost_efficiency", "platform_throughput"] });
  });

  it("removes just the toggled key, leaving the rest", () => {
    const p = fixture();
    const cost = nodeById(p, "qualitative:cost_efficiency");
    expect(
      narrow({ qualitative: ["cost_efficiency", "platform_throughput"] }, cost, {
        additive: true,
      }),
    ).toEqual({ qualitative: ["platform_throughput"] });
  });

  it("clears the pillar when the last OR'd key is toggled off", () => {
    const p = fixture();
    const cost = nodeById(p, "qualitative:cost_efficiency");
    expect(narrow({ qualitative: ["cost_efficiency"] }, cost, { additive: true })).toEqual({});
  });

  it("seeds a pillar from empty on the first shift-click", () => {
    const p = fixture();
    const cost = nodeById(p, "qualitative:cost_efficiency");
    expect(narrow({}, cost, { additive: true })).toEqual({
      qualitative: ["cost_efficiency"],
    });
  });
});
