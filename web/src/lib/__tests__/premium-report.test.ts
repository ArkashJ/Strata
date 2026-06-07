import { describe, expect, it } from "vitest";

import {
  bridgeScenario,
  dedupeInputs,
  factorChain,
  kpiFigures,
  methodEstimates,
} from "@/lib/premium-report";
import type { InputUsed, Scenario, TAMOutput, Unit } from "@/lib/schemas";

const USD: Unit = { kind: "money", dimension: "currency", currency: "USD" };
const COUNT: Unit = { kind: "count", dimension: "count" };
const RATIO: Unit = { kind: "ratio", dimension: "ratio" };

function input(over: Partial<InputUsed>): InputUsed {
  return {
    role_name: "x",
    role: "base_value",
    primitive_slug: "p",
    snapshot_sha256: "abc",
    value: 1,
    name: "X",
    unit: COUNT,
    source_tier: "regulator",
    source_url: null,
    ...over,
  };
}

function scenario(over: Partial<Scenario>): Scenario {
  return {
    definition: "d",
    lens: "latent_demand",
    framework: "latent-demand-v1",
    framework_variant: null,
    value: 100,
    unit: USD,
    inputs_used: [],
    assumptions: {},
    banners: [],
    ...over,
  };
}

function tam(over: Partial<TAMOutput>): TAMOutput {
  return {
    kind: "tam_output",
    state_hash: "h".repeat(32),
    schema_version: 2,
    created_by: "t",
    created_at: "2026-06-07T00:00:00Z",
    target: { concept: "c", expansion_stage: "current" },
    scenarios: [scenario({})],
    method_families_used: ["top_down_spend"],
    convergence: null,
    independence_score: 0.5,
    uses_synthetic_primitives: false,
    uses_modeled_composites: false,
    scope: null,
    ...over,
  };
}

describe("dedupeInputs", () => {
  it("keeps the first occurrence per primitive across scenarios", () => {
    const t = tam({
      scenarios: [
        scenario({ inputs_used: [input({ primitive_slug: "a" }), input({ primitive_slug: "b" })] }),
        scenario({ inputs_used: [input({ primitive_slug: "a" }), input({ primitive_slug: "c" })] }),
      ],
    });
    expect(dedupeInputs(t).map((i) => i.primitive_slug)).toEqual(["a", "b", "c"]);
  });
});

describe("factorChain", () => {
  it("returns a chain for a multiplicative lens with ≥2 sourced factors", () => {
    const s = scenario({
      lens: "latent_demand",
      value: 600,
      inputs_used: [
        input({ primitive_slug: "pop", value: 20, unit: COUNT }),
        input({ primitive_slug: "adopt", value: 0.3, unit: RATIO }),
        input({ primitive_slug: "wtp", value: 100, unit: USD }),
      ],
    });
    const chain = factorChain(s);
    expect(chain?.steps).toHaveLength(3);
    expect(chain?.total).toBe(600);
  });

  it("returns null for a non-multiplicative lens (never invents a chain)", () => {
    const s = scenario({
      lens: "bundle_consolidation",
      inputs_used: [input({ value: 1 }), input({ value: 2 })],
    });
    expect(factorChain(s)).toBeNull();
  });

  it("returns null when fewer than 2 factors carry a value", () => {
    const s = scenario({
      lens: "latent_demand",
      inputs_used: [input({ value: 1 }), input({ value: null })],
    });
    expect(factorChain(s)).toBeNull();
  });
});

describe("bridgeScenario", () => {
  it("picks the multiplicative scenario with the most sourced factors", () => {
    const t = tam({
      scenarios: [
        scenario({ lens: "bundle_consolidation", inputs_used: [input({ value: 1 })] }),
        scenario({
          framework: "rich",
          lens: "latent_demand",
          inputs_used: [input({ value: 1 }), input({ value: 2 }), input({ value: 3 })],
        }),
      ],
    });
    expect(bridgeScenario(t)?.scenario.framework).toBe("rich");
  });

  it("returns null when no scenario qualifies", () => {
    expect(
      bridgeScenario(tam({ scenarios: [scenario({ lens: "bundle_consolidation" })] })),
    ).toBeNull();
  });
});

describe("methodEstimates", () => {
  it("emits one estimate per scenario", () => {
    const t = tam({ scenarios: [scenario({ value: 1 }), scenario({ framework: "b", value: 2 })] });
    expect(methodEstimates(t)).toHaveLength(2);
  });
});

describe("kpiFigures", () => {
  it("flags modeled when the TAM leans on modeled composites", () => {
    expect(kpiFigures(tam({ uses_modeled_composites: true })).modeled).toBe(true);
    expect(kpiFigures(tam({})).modeled).toBe(false);
  });

  it("reports a single point for a degenerate scenario set", () => {
    expect(kpiFigures(tam({ scenarios: [scenario({ value: 100 })] })).range).toBe("single point");
  });
});
