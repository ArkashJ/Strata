import { describe, expect, it } from "vitest";

import { rankByQuery } from "../fuzzy";

const id = (s: string) => s;

describe("rankByQuery", () => {
  it("returns every item for an empty query, preserving order", () => {
    const items = ["gamma", "alpha", "beta"];
    expect(rankByQuery(items, "", id).map((s) => s.item)).toEqual(items);
  });

  it("ranks exact match above prefix above substring above subsequence", () => {
    const items = ["doc", "doc-gen", "endoctrinate", "dxoxc"];
    const ranked = rankByQuery(items, "doc", id).map((s) => s.item);
    expect(ranked[0]).toBe("doc"); // exact
    expect(ranked[1]).toBe("doc-gen"); // prefix
    expect(ranked.indexOf("endoctrinate")).toBeGreaterThan(ranked.indexOf("doc-gen")); // substring
    expect(ranked.indexOf("dxoxc")).toBeGreaterThan(ranked.indexOf("endoctrinate")); // subsequence
  });

  it("excludes non-matches", () => {
    const ranked = rankByQuery(["alpha", "beta"], "zzz", id);
    expect(ranked).toHaveLength(0);
  });

  it("is case-insensitive", () => {
    expect(rankByQuery(["Bottoms-Up Cost Efficiency"], "cost", id)).toHaveLength(1);
  });

  it("ranks an earlier substring above a later one", () => {
    const ranked = rankByQuery(["xxxcost", "costxxx"], "cost", id).map((s) => s.item);
    expect(ranked[0]).toBe("costxxx");
  });

  it("works with a keyFn over objects", () => {
    const items = [{ name: "FRED GDP" }, { name: "BLS CPI" }];
    const ranked = rankByQuery(items, "gdp", (x) => x.name);
    expect(ranked).toHaveLength(1);
    expect(ranked[0].item.name).toBe("FRED GDP");
  });

  it("keeps original order for tied scores (stable)", () => {
    const items = ["aaa-cost", "bbb-cost"]; // both contiguous substring at same index
    const ranked = rankByQuery(items, "cost", id).map((s) => s.item);
    expect(ranked).toEqual(["aaa-cost", "bbb-cost"]);
  });
});
