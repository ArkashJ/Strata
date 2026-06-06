import { describe, expect, it } from "vitest";

import { type BuildStep, deriveBuildSteps, stepIndexForRole } from "../build-studio";
import type { InputUsed, Scenario, TAMOutput, Unit } from "../schemas";
import type { BuildState } from "../state-hash";

const USD: Unit = { kind: "money", dimension: "currency", currency: "USD" };

function input(slug: string, value: number | null, over: Partial<InputUsed> = {}): InputUsed {
  return {
    role_name: `role for ${slug}`,
    role: "base_value",
    primitive_slug: slug,
    snapshot_sha256: "ab".repeat(32),
    value,
    name: `Name ${slug}`,
    unit: USD,
    source_tier: "regulator",
    source_url: `https://example.gov/${slug}`,
    ...over,
  };
}

function scenario(
  framework: string,
  lens: Scenario["lens"],
  value: number,
  inputs: InputUsed[],
): Scenario {
  return {
    definition: `${framework} def`,
    lens,
    framework,
    value,
    unit: USD,
    inputs_used: inputs,
    assumptions: {},
    banners: [],
  };
}

function tam(scenarios: Scenario[]): TAMOutput {
  return {
    kind: "tam_output",
    state_hash: "deadbeef",
    schema_version: 1,
    created_by: "test",
    created_at: "2026-06-06T00:00:00Z",
    target: { concept: "ai-sales-ops", concept_name: "AI Sales Ops", expansion_stage: "current" },
    scenarios,
    method_families_used: ["bottoms_up_seats"],
    independence_score: 1,
    uses_synthetic_primitives: false,
    uses_modeled_composites: false,
  };
}

function state(): BuildState {
  return {
    target_concept_slug: "ai-sales-ops",
    frameworks_selected: [],
    framework_assumptions: {},
    primitive_pins: {},
    primitive_overrides: {},
  };
}

const byKind = (steps: BuildStep[], kind: BuildStep["kind"]) =>
  steps.filter((s) => s.kind === kind);

describe("deriveBuildSteps", () => {
  it("emits the apex first, then framework, then its role leaves", () => {
    const t = tam([
      scenario("seats-fw", "cost_efficiency", 200, [input("seats", 10), input("cost", 20)]),
    ]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());

    expect(steps[0].kind).toBe("apex");
    expect(steps[0].id).toBe("target");
    expect(steps[1].kind).toBe("framework");
    expect(steps[1].id).toBe("f-seats-fw");
    expect(steps[2].kind).toBe("role");
    expect(steps[3].kind).toBe("role");
    expect(steps.map((s) => s.id)).toEqual([
      "target",
      "f-seats-fw",
      "p-f-seats-fw-seats",
      "p-f-seats-fw-cost",
    ]);
  });

  it("emits exactly one step per consumed base_value role", () => {
    const t = tam([scenario("fw", "cost_efficiency", 6, [input("a", 2), input("b", 3)])]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(byKind(steps, "role")).toHaveLength(2);
  });

  it("ignores non-base_value inputs (only the multiplicative leaves reveal)", () => {
    const growth = input("growth", 1.2, { role: "growth_index" });
    const t = tam([scenario("fw", "cost_efficiency", 12, [input("seats", 10), growth])]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(byKind(steps, "role").map((s) => s.id)).toEqual(["p-f-fw-seats"]);
  });

  it("apex runningValue is the mean of the lens's scenario values", () => {
    const t = tam([
      scenario("a", "cost_efficiency", 100, [input("x", 100)]),
      scenario("b", "cost_efficiency", 300, [input("y", 300)]),
    ]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(steps[0].runningValue).toBe(200);
  });

  it("role runningValue is the running partial product of base_value inputs", () => {
    const t = tam([
      scenario("fw", "cost_efficiency", 30, [input("a", 2), input("b", 5), input("c", 3)]),
    ]);
    const roles = byKind(deriveBuildSteps(t, "cost_efficiency", state()), "role");
    expect(roles.map((s) => s.runningValue)).toEqual([2, 10, 30]);
  });

  it("filters to the chosen lens only", () => {
    const t = tam([
      scenario("cost-fw", "cost_efficiency", 100, [input("a", 100)]),
      scenario("rev-fw", "revenue_generation", 500, [input("b", 500)]),
    ]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(steps.some((s) => s.frameworkSlug === "rev-fw")).toBe(false);
    expect(steps.find((s) => s.kind === "framework")?.id).toBe("f-cost-fw");
  });

  it("returns an empty script for a lens with no applicable scenarios (no theater)", () => {
    const t = tam([scenario("fw", "cost_efficiency", 100, [input("a", 100)])]);
    expect(deriveBuildSteps(t, "latent_demand", state())).toEqual([]);
  });

  it("orders frameworks so the most-divergent method reveals LAST", () => {
    const t = tam([
      scenario("far", "cost_efficiency", 1000, [input("a", 1000)]),
      scenario("near", "cost_efficiency", 100, [input("b", 100)]),
      scenario("mid", "cost_efficiency", 90, [input("c", 90)]),
    ]);
    // mean = 1190/3 ≈ 396.7; distances: near≈296.7, mid≈306.7, far≈603.3
    const fwIds = byKind(deriveBuildSteps(t, "cost_efficiency", state()), "framework").map(
      (s) => s.id,
    );
    expect(fwIds[fwIds.length - 1]).toBe("f-far");
  });

  it("carries number-level provenance onto each role step", () => {
    const t = tam([
      scenario("fw", "cost_efficiency", 10, [
        input("seats", 10, {
          source_url: "https://bls.gov/seats",
          source_tier: "regulator",
          snapshot_sha256: "cd".repeat(32),
        }),
      ]),
    ]);
    const role = byKind(deriveBuildSteps(t, "cost_efficiency", state()), "role")[0];
    expect(role.sourceUrl).toBe("https://bls.gov/seats");
    expect(role.tier).toBe("regulator");
    expect(role.snapshot).toBe("cd".repeat(32));
    expect(role.value).toBe(10);
  });

  it("flags modeled / composite inputs honestly (null url, null tier)", () => {
    const t = tam([
      scenario("fw", "cost_efficiency", 5, [
        input("composite", 5, { source_url: null, source_tier: null }),
      ]),
    ]);
    const role = byKind(deriveBuildSteps(t, "cost_efficiency", state()), "role")[0];
    expect(role.sourceUrl).toBeNull();
    expect(role.tier).toBeNull();
  });

  it("treats a null-valued input as a factor of 1 (chain never collapses to 0)", () => {
    const t = tam([
      scenario("fw", "cost_efficiency", 10, [input("known", 10), input("unknown", null)]),
    ]);
    const roles = byKind(deriveBuildSteps(t, "cost_efficiency", state()), "role");
    expect(roles.map((s) => s.runningValue)).toEqual([10, 10]);
  });

  it("is deterministic — same TAM + lens + state yields identical scripts", () => {
    const t = tam([
      scenario("a", "cost_efficiency", 300, [input("x", 300)]),
      scenario("b", "cost_efficiency", 100, [input("y", 100)]),
    ]);
    const a = deriveBuildSteps(t, "cost_efficiency", state());
    const b = deriveBuildSteps(t, "cost_efficiency", state());
    expect(a).toEqual(b);
  });
});

describe("stepIndexForRole", () => {
  it("returns the cursor index of the steered role leaf", () => {
    const t = tam([scenario("fw", "cost_efficiency", 6, [input("a", 2), input("b", 3)])]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(stepIndexForRole(steps, "b")).toBe(3);
  });

  it("returns the step count (reveal-all) when the slug is absent — never rewinds", () => {
    const t = tam([scenario("fw", "cost_efficiency", 2, [input("a", 2)])]);
    const steps = deriveBuildSteps(t, "cost_efficiency", state());
    expect(stepIndexForRole(steps, "nope")).toBe(steps.length);
  });
});
