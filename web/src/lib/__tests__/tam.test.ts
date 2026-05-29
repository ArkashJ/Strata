import { describe, expect, it } from "vitest";

import { type Scenario, type TAMOutput, tamOutputSchema } from "../schemas";
import { isDegenerate, midScenario, tamRange, tamToMarkdown } from "../tam";

const currencyUnit = {
  kind: "flow",
  dimension: "currency",
  denominator: "per-year",
  currency: "USD",
  basis: "nominal",
};

function scenario(definition: string, value: number): Scenario {
  return {
    definition,
    lens: "cost_efficiency",
    framework: "bottoms-up-cost-efficiency",
    framework_variant: null,
    value,
    unit: currencyUnit,
    inputs_used: [],
    assumptions: {},
    banners: [],
  };
}

function tam(values: number[]): TAMOutput {
  return tamOutputSchema.parse({
    kind: "tam_output",
    state_hash: "abc123",
    schema_version: 1,
    created_by: "tester",
    created_at: "2026-05-28T00:00:00Z",
    target: {
      concept: "doc-gen-pc-insurance",
      concept_name: "P&C doc-gen",
      geo: "US",
      time: "2026",
      expansion_stage: "n/a",
    },
    scenarios: values.map((v, i) => scenario(`scenario-${i}`, v)),
    method_families_used: ["bottoms_up_seats"],
    independence_score: 0.5,
    uses_synthetic_primitives: false,
    uses_modeled_composites: false,
  });
}

describe("isDegenerate", () => {
  it("is degenerate with a single scenario", () => {
    expect(isDegenerate(tam([100]))).toBe(true);
  });

  it("is degenerate when all scenarios share a value", () => {
    expect(isDegenerate(tam([100, 100, 100]))).toBe(true);
  });

  it("is not degenerate with a real spread", () => {
    expect(isDegenerate(tam([100, 200, 300]))).toBe(false);
  });
});

describe("midScenario", () => {
  it("returns the median-positioned scenario by value", () => {
    const mid = midScenario(tam([300, 100, 200]));
    expect(mid.value).toBe(200);
  });
});

describe("tamRange", () => {
  it("reports low / high / mid", () => {
    const r = tamRange(tam([300, 100, 200]));
    expect(r.low).toBe(100);
    expect(r.high).toBe(300);
    expect(r.mid).toBe(200);
  });

  it("uses the mean for an even pair, not the lower scenario", () => {
    const r = tamRange(tam([470, 155]));
    expect(r.low).toBe(155);
    expect(r.high).toBe(470);
    expect(r.mid).toBe(312.5);
  });

  it("collapses to a point for a single scenario", () => {
    const r = tamRange(tam([42]));
    expect(r).toEqual({ low: 42, high: 42, mid: 42 });
  });
});

describe("tamToMarkdown", () => {
  it("renders headline, range, scenario table, and method", () => {
    const md = tamToMarkdown(tam([1_000_000_000, 2_000_000_000, 3_000_000_000]));
    expect(md).toContain("# TAM: P&C doc-gen");
    expect(md).toContain("**Mid estimate:**");
    expect(md).toContain("**Range:**");
    expect(md).toContain("| Scenario | Framework | Value |");
    expect(md).toContain("Independence score: 0.50");
    expect(md).toContain("`abc123`");
  });

  it("omits the range line for a degenerate TAM", () => {
    const md = tamToMarkdown(tam([5_000_000]));
    expect(md).not.toContain("**Range:**");
  });

  it("surfaces synthetic + modeled banners as notes", () => {
    const t = tamOutputSchema.parse({
      ...tam([100, 200]),
      uses_synthetic_primitives: true,
      uses_modeled_composites: true,
    });
    const md = tamToMarkdown(t);
    expect(md).toContain("## Notes");
    expect(md).toContain("synthetic");
    expect(md).toContain("modeled");
  });
});
