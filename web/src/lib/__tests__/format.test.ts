import { describe, expect, it } from "vitest";

import { formatCompact, formatUSD, lensLabel, tierLabel } from "../format";

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
