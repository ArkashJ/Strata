import { describe, expect, it } from "vitest";

import { hasOverrides, needsRecompute } from "../queries";
import type { BuildState } from "../state-hash";

// needsRecompute is the gate that routes a /build state to POST /build/recompute
// (diverged) vs GET /build/{slug} (registry default): true when the user has a
// what-if/swap (hasOverrides) OR a pinned market (non-empty scope). hasOverrides
// is one input to it. Neither must treat an empty inner assumptions map — or an
// empty scope — as a divergence, or every fresh concept open would fire a
// needless recompute.
function base(): BuildState {
  return {
    target_concept_slug: "ai-coding-assistants-us",
    frameworks_selected: [],
    framework_assumptions: {},
    primitive_pins: {},
    primitive_overrides: {},
  };
}

describe("hasOverrides", () => {
  it("is false for a fresh concept state (no overrides)", () => {
    expect(hasOverrides(base())).toBe(false);
  });

  it("is false when framework_assumptions has only empty inner maps", () => {
    expect(hasOverrides({ ...base(), framework_assumptions: { "some-fw": {} } })).toBe(false);
  });

  it("is true with a what-if scalar override", () => {
    const state: BuildState = {
      ...base(),
      primitive_overrides: {
        "wtp-per-seat": { value: 50, unit: { kind: "currency", dimension: "money" } },
      },
    };
    expect(hasOverrides(state)).toBe(true);
  });

  it("is true with a populated framework_assumptions swap", () => {
    const state: BuildState = {
      ...base(),
      framework_assumptions: {
        "bottoms-up-cost-efficiency": { cost_per_persona: "other-primitive" },
      },
    };
    expect(hasOverrides(state)).toBe(true);
  });
});

describe("needsRecompute", () => {
  it("is false for a fresh, unscoped concept state (GET /build/{slug} suffices)", () => {
    expect(needsRecompute(base())).toBe(false);
  });

  it("is true on a what-if/swap even without a pinned market", () => {
    const state: BuildState = {
      ...base(),
      primitive_overrides: {
        "wtp-per-seat": { value: 50, unit: { kind: "currency", dimension: "money" } },
      },
    };
    expect(needsRecompute(state)).toBe(true);
  });

  it("is true on a pinned market even with no overrides (GET ignores scope)", () => {
    const state: BuildState = {
      ...base(),
      scope: {
        vertical: [],
        persona: [],
        segment: { min_emp: 100, max_emp: 999, label: "Mid-market (100–999)" },
        geo_supply: [],
        geo_demand: [],
        product: [],
        include: [],
        exclude: [],
      },
    };
    expect(needsRecompute(state)).toBe(true);
  });

  it("is false for an all-empty pinned scope (back-compat with the unscoped path)", () => {
    const state: BuildState = {
      ...base(),
      scope: {
        vertical: [],
        persona: [],
        segment: null,
        geo_supply: [],
        geo_demand: [],
        product: [],
        include: [],
        exclude: [],
      },
    };
    expect(needsRecompute(state)).toBe(false);
  });
});
