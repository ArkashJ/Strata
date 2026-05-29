import { describe, expect, it } from "vitest";

import {
  type BuildState,
  canonicalizeState,
  decodeState,
  encodeState,
  hashState,
} from "../state-hash";

function baseState(): BuildState {
  return {
    target_concept_slug: "doc-gen-pc-insurance",
    geo: "US",
    time: "2026",
    expansion_stage: "n/a",
    frameworks_selected: ["bottoms-up-cost-efficiency"],
    framework_assumptions: {},
    primitive_pins: {},
  };
}

describe("canonicalizeState", () => {
  it("is order-independent across object-key insertion order", () => {
    const a: BuildState = {
      target_concept_slug: "x",
      geo: "US",
      time: null,
      expansion_stage: null,
      frameworks_selected: [],
      framework_assumptions: { f: { persona_pool: "p1", cost_per_persona: "p2" } },
      primitive_pins: { slot_a: "p1", slot_b: "p2" },
    };
    // Same logical state, keys built in a different order.
    const b: BuildState = {
      primitive_pins: { slot_b: "p2", slot_a: "p1" },
      framework_assumptions: { f: { cost_per_persona: "p2", persona_pool: "p1" } },
      frameworks_selected: [],
      expansion_stage: null,
      time: null,
      geo: "US",
      target_concept_slug: "x",
    } as BuildState;
    expect(canonicalizeState(a)).toBe(canonicalizeState(b));
  });

  it("treats frameworks_selected as a set (ordering collides)", () => {
    const a = { ...baseState(), frameworks_selected: ["alpha", "beta"] };
    const b = { ...baseState(), frameworks_selected: ["beta", "alpha"] };
    expect(canonicalizeState(a)).toBe(canonicalizeState(b));
  });

  it("normalizes missing optional fields to null", () => {
    const withNulls = { ...baseState(), geo: null, time: null, expansion_stage: null };
    const withUndef: BuildState = {
      target_concept_slug: baseState().target_concept_slug,
      frameworks_selected: baseState().frameworks_selected,
      framework_assumptions: {},
      primitive_pins: {},
    };
    expect(canonicalizeState(withNulls)).toBe(canonicalizeState(withUndef));
  });

  it("distinguishes genuinely different states", () => {
    const a = baseState();
    const b = { ...baseState(), geo: "EU" };
    expect(canonicalizeState(a)).not.toBe(canonicalizeState(b));
  });
});

describe("hashState", () => {
  it("returns 64 lowercase hex chars", async () => {
    const hash = await hashState(baseState());
    expect(hash).toMatch(/^[a-f0-9]{64}$/);
  });

  it("equal canonical states produce equal hashes", async () => {
    const a = { ...baseState(), frameworks_selected: ["a", "b"] };
    const b = { ...baseState(), frameworks_selected: ["b", "a"] };
    expect(await hashState(a)).toBe(await hashState(b));
  });

  it("different states produce different hashes", async () => {
    expect(await hashState(baseState())).not.toBe(
      await hashState({ ...baseState(), time: "2027" }),
    );
  });

  it("is a known SHA-256 of its canonical form", async () => {
    const s = baseState();
    const expected = await crypto.subtle
      .digest("SHA-256", new TextEncoder().encode(canonicalizeState(s)))
      .then((buf) =>
        Array.from(new Uint8Array(buf))
          .map((b) => b.toString(16).padStart(2, "0"))
          .join(""),
      );
    expect(await hashState(s)).toBe(expected);
  });
});

describe("encodeState / decodeState", () => {
  it("round-trips a state", () => {
    const s = baseState();
    const decoded = decodeState(encodeState(s));
    // decode produces the canonical (normalized) shape
    expect(decoded.target_concept_slug).toBe(s.target_concept_slug);
    expect(decoded.geo).toBe("US");
    expect(decoded.frameworks_selected).toEqual(["bottoms-up-cost-efficiency"]);
  });

  it("produces URL-safe output (no + / = chars)", () => {
    const s: BuildState = {
      ...baseState(),
      framework_assumptions: { "f/g": { "a+b": "c/d", e: "f==g" } },
    };
    const encoded = encodeState(s);
    expect(encoded).not.toMatch(/[+/=]/);
  });

  it("survives multi-byte characters", () => {
    const s = { ...baseState(), time: "2026-Σ-π" };
    expect(decodeState(encodeState(s)).time).toBe("2026-Σ-π");
  });

  it("equivalent states encode identically", () => {
    const a = { ...baseState(), frameworks_selected: ["a", "b"] };
    const b = { ...baseState(), frameworks_selected: ["b", "a"] };
    expect(encodeState(a)).toBe(encodeState(b));
  });
});
