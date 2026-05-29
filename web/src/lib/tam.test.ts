import { describe, expect, it } from "vitest";

import type { TrajectoryPoint } from "./schemas";
import { trajectoryDelta } from "./tam";

function point(value: number, low = value, high = value): TrajectoryPoint {
  return {
    as_of: "2026-01-01",
    value,
    low,
    high,
    method_families: ["top_down_spend"],
    scenarios_n: 1,
  };
}

describe("trajectoryDelta", () => {
  it("returns null for an empty series", () => {
    expect(trajectoryDelta([])).toBeNull();
  });

  it("returns null for a single point (no prior to compare against)", () => {
    expect(trajectoryDelta([point(100)])).toBeNull();
  });

  it("computes an upward delta against the prior point", () => {
    const delta = trajectoryDelta([point(100), point(125)]);
    expect(delta).not.toBeNull();
    expect(delta?.direction).toBe("up");
    expect(delta?.pct).toBeCloseTo(0.25);
  });

  it("computes a downward delta against the prior point", () => {
    const delta = trajectoryDelta([point(200), point(150)]);
    expect(delta?.direction).toBe("down");
    expect(delta?.pct).toBeCloseTo(-0.25);
  });

  it("reports a flat move as flat with zero pct", () => {
    const delta = trajectoryDelta([point(100), point(100)]);
    expect(delta?.direction).toBe("flat");
    expect(delta?.pct).toBe(0);
  });

  it("compares only the last two points, ignoring earlier history", () => {
    const delta = trajectoryDelta([point(10), point(1000), point(1100)]);
    expect(delta?.pct).toBeCloseTo(0.1);
  });

  it("returns null when the prior value is zero (undefined %)", () => {
    expect(trajectoryDelta([point(0), point(50)])).toBeNull();
  });
});
