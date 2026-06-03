import { describe, expect, it } from "vitest";

import type { MarketScope } from "../schemas";
import {
  type BuildState,
  canonicalizeState,
  decodeState,
  encodeState,
  hashState,
  isScopeEmpty,
} from "../state-hash";

function emptyScope(): MarketScope {
  return {
    vertical: [],
    persona: [],
    segment: null,
    geo_supply: [],
    geo_demand: [],
    product: [],
    include: [],
    exclude: [],
  };
}

const MID_MARKET = { min_emp: 100, max_emp: 999, label: "Mid-market (100–999)" };

function baseState(): BuildState {
  return {
    target_concept_slug: "doc-gen-pc-insurance",
    geo: "US",
    time: "2026",
    expansion_stage: "n/a",
    frameworks_selected: ["bottoms-up-cost-efficiency"],
    framework_assumptions: {},
    primitive_pins: {},
    primitive_overrides: {},
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
      primitive_overrides: {},
    };
    // Same logical state, keys built in a different order.
    const b: BuildState = {
      primitive_overrides: {},
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
      primitive_overrides: {},
    };
    expect(canonicalizeState(withNulls)).toBe(canonicalizeState(withUndef));
  });

  it("distinguishes genuinely different states", () => {
    const a = baseState();
    const b = { ...baseState(), geo: "EU" };
    expect(canonicalizeState(a)).not.toBe(canonicalizeState(b));
  });

  it("a what-if override changes the canonical state (and thus the hash)", () => {
    const base = baseState();
    const withOverride: BuildState = {
      ...base,
      primitive_overrides: {
        "wtp-per-seat": { value: 50, unit: { kind: "currency", dimension: "money" } },
      },
    };
    expect(canonicalizeState(base)).not.toBe(canonicalizeState(withOverride));
  });

  // ── pinned market scope (sub-project 1.5) ───────────────────────────────────
  it("an empty/absent scope canonicalizes identically to no scope (back-compat)", () => {
    const noScope = baseState();
    const withEmpty: BuildState = { ...baseState(), scope: emptyScope() };
    const withNull: BuildState = { ...baseState(), scope: null };
    // Unscoped states must keep producing today's exact canonical bytes, so
    // every pre-scope /build/<hash> URL still round-trips.
    expect(canonicalizeState(withEmpty)).toBe(canonicalizeState(noScope));
    expect(canonicalizeState(withNull)).toBe(canonicalizeState(noScope));
  });

  it("a pinned market changes the canonical state (a different market is a different build)", () => {
    const base = baseState();
    const pinned: BuildState = {
      ...base,
      scope: { ...emptyScope(), segment: MID_MARKET },
    };
    expect(canonicalizeState(base)).not.toBe(canonicalizeState(pinned));
  });

  it("two logically-equal scopes collide regardless of tag order", () => {
    const a: BuildState = {
      ...baseState(),
      scope: {
        ...emptyScope(),
        vertical: [
          { system: "NAICS", code: "5411", label: "Legal" },
          { system: "NAICS", code: "5415", label: "Computer systems" },
        ],
        geo_demand: ["US", "CA"],
      },
    };
    const b: BuildState = {
      ...baseState(),
      scope: {
        ...emptyScope(),
        vertical: [
          { system: "NAICS", code: "5415", label: "Computer systems" },
          { system: "NAICS", code: "5411", label: "Legal" },
        ],
        geo_demand: ["CA", "US"],
      },
    };
    expect(canonicalizeState(a)).toBe(canonicalizeState(b));
  });

  it("distinguishes two different pinned markets", () => {
    const smb: BuildState = {
      ...baseState(),
      scope: { ...emptyScope(), segment: { min_emp: null, max_emp: 99, label: "SMB (<100)" } },
    };
    const ent: BuildState = {
      ...baseState(),
      scope: { ...emptyScope(), segment: { min_emp: 1000, max_emp: null, label: "Enterprise" } },
    };
    expect(canonicalizeState(smb)).not.toBe(canonicalizeState(ent));
  });
});

describe("isScopeEmpty", () => {
  it("is true for null/undefined and an all-empty scope", () => {
    expect(isScopeEmpty(null)).toBe(true);
    expect(isScopeEmpty(undefined)).toBe(true);
    expect(isScopeEmpty(emptyScope())).toBe(true);
  });

  it("is false once any dimension is pinned", () => {
    expect(isScopeEmpty({ ...emptyScope(), segment: MID_MARKET })).toBe(false);
    expect(isScopeEmpty({ ...emptyScope(), geo_demand: ["US"] })).toBe(false);
    expect(
      isScopeEmpty({
        ...emptyScope(),
        vertical: [{ system: "NAICS", code: "5411", label: "Legal" }],
      }),
    ).toBe(false);
  });
});

describe("encode/decode preserves a pinned scope", () => {
  it("round-trips the market through ?s=", () => {
    const s: BuildState = {
      ...baseState(),
      scope: { ...emptyScope(), segment: MID_MARKET, geo_demand: ["US"] },
    };
    const decoded = decodeState(encodeState(s));
    expect(decoded.scope?.segment?.label).toBe("Mid-market (100–999)");
    expect(decoded.scope?.geo_demand).toEqual(["US"]);
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
