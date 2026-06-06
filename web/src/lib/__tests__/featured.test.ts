import { describe, expect, it } from "vitest";

import { FEATURED_CONCEPT_SLUGS, selectFeaturedSlugs } from "../featured";

const concept = (slug: string) => ({ slug });

describe("selectFeaturedSlugs", () => {
  it("returns the curated allowlist in order when all exist", () => {
    const concepts = [
      concept("doc-gen-pc-insurance"),
      concept("kyber-pc-doc-gen"),
      concept("effective-ai-insurance-knowledge"),
      concept("some-other-concept"),
    ];
    expect(selectFeaturedSlugs(concepts)).toEqual([...FEATURED_CONCEPT_SLUGS]);
  });

  it("tops up from remaining concepts when an allowlisted slug is missing", () => {
    const concepts = [concept("kyber-pc-doc-gen"), concept("fallback-a"), concept("fallback-b")];
    const picked = selectFeaturedSlugs(concepts);
    // Allowlist hits first (in allowlist order), then concept-order fallbacks.
    expect(picked).toEqual(["kyber-pc-doc-gen", "fallback-a", "fallback-b"]);
  });

  it("honors a non-default count (truncation + top-up boundary)", () => {
    const concepts = [concept("kyber-pc-doc-gen"), concept("a"), concept("b")];
    expect(selectFeaturedSlugs(concepts, 2)).toEqual(["kyber-pc-doc-gen", "a"]);
  });

  it("does not crash or duplicate when fewer than count concepts exist", () => {
    expect(selectFeaturedSlugs([concept("kyber-pc-doc-gen")])).toEqual(["kyber-pc-doc-gen"]);
    expect(selectFeaturedSlugs([])).toEqual([]);
  });

  it("never returns duplicates", () => {
    const concepts = [concept("kyber-pc-doc-gen"), concept("kyber-pc-doc-gen")];
    expect(selectFeaturedSlugs(concepts)).toEqual(["kyber-pc-doc-gen"]);
  });
});
