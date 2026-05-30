import { describe, expect, it } from "vitest";

import { hasOverrides } from "../queries";
import type { BuildState } from "../state-hash";

// hasOverrides is the gate that routes a /build state to POST /build/recompute
// (diverged) vs GET /build/{slug} (registry default). Its branch logic must not
// treat an empty inner assumptions map as a divergence, or every fresh concept
// open would fire a needless recompute.
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
