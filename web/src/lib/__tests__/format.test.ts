import { describe, expect, it } from "vitest";

import {
  formatCompact,
  formatSnapshot,
  formatUSD,
  isPlaceholderSnapshot,
  lensLabel,
  tierLabel,
} from "../format";

describe("formatUSD", () => {
  it("formats billions / millions / thousands", () => {
    expect(formatUSD(2_500_000_000)).toBe("$2.50B");
    expect(formatUSD(3_000_000)).toBe("$3M");
    expect(formatUSD(4_000)).toBe("$4K");
  });

  it("formats small values with locale separators", () => {
    expect(formatUSD(950)).toBe("$950");
  });

  it("handles negatives", () => {
    expect(formatUSD(-1_000_000)).toBe("-$1M");
  });

  it("returns an em dash for non-finite input", () => {
    expect(formatUSD(Number.POSITIVE_INFINITY)).toBe("—");
    expect(formatUSD(Number.NaN)).toBe("—");
  });
});

describe("formatCompact", () => {
  it("delegates to USD for currency dimension", () => {
    expect(formatCompact(2_500_000_000, { dimension: "currency" })).toBe("$2.50B");
  });

  it("uses compact notation for non-currency", () => {
    expect(formatCompact(322_500, { dimension: "people" })).toBe("322.5K");
  });

  it("appends a denominator suffix", () => {
    expect(formatCompact(100, { dimension: "people", denominator: "year" })).toBe("100/year");
  });

  it("returns an em dash for non-finite input", () => {
    expect(formatCompact(Number.NaN)).toBe("—");
  });
});

describe("tierLabel", () => {
  it("title-cases underscore and hyphen tiers", () => {
    expect(tierLabel("first_party")).toBe("First Party");
    expect(tierLabel("analyst-paraphrase")).toBe("Analyst Paraphrase");
  });
});

describe("lensLabel", () => {
  it("title-cases underscore lenses", () => {
    expect(lensLabel("cost_efficiency")).toBe("Cost Efficiency");
  });
});

describe("isPlaceholderSnapshot", () => {
  const realHash = "b9ee1e4978ed783523f417a2fbbeb4d72295695407d7713c72e529175aacb821";

  it("flags the all-d3 demo sentinel", () => {
    expect(isPlaceholderSnapshot("d3".repeat(32))).toBe(true);
  });

  it("flags any single-hex-pair-repeated sentinel", () => {
    expect(isPlaceholderSnapshot("ab".repeat(32))).toBe(true);
  });

  it("flags a too-short hash", () => {
    expect(isPlaceholderSnapshot("d3d3d3")).toBe(true);
  });

  it("accepts a genuine 64-hex content pin", () => {
    expect(isPlaceholderSnapshot(realHash)).toBe(false);
  });

  it("treats an absent snapshot as not-a-placeholder (caller renders em-dash)", () => {
    expect(isPlaceholderSnapshot(null)).toBe(false);
    expect(isPlaceholderSnapshot(undefined)).toBe(false);
    expect(isPlaceholderSnapshot("")).toBe(false);
  });
});

describe("formatSnapshot", () => {
  const realHash = "b9ee1e4978ed783523f417a2fbbeb4d72295695407d7713c72e529175aacb821";

  it("renders an honest marker for the demo sentinel, never the fake hash", () => {
    expect(formatSnapshot("d3".repeat(32))).toBe("not pinned (demo)");
  });

  it("renders the short hash for a genuine pin", () => {
    expect(formatSnapshot(realHash)).toBe("b9ee1e4978");
  });

  it("renders the honest marker for a present-but-too-short hash", () => {
    expect(formatSnapshot("d3d3d3")).toBe("not pinned (demo)");
  });

  it("renders an em-dash for an absent snapshot (composite input)", () => {
    expect(formatSnapshot(null)).toBe("—");
  });
});
