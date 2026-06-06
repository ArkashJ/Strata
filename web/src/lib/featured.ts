// Homepage "featured" concepts. First contact must put Strata's *sourced* foot
// forward — not whatever happens to sort first. These three were picked by
// regulator/aggregator-input ratio across their live TAM (PR 0 trust pass):
//
//   kyber-pc-doc-gen                 100% sourced (2/2)
//   effective-ai-insurance-knowledge 100% sourced (2/2)
//   doc-gen-pc-insurance              75% sourced (3/4)
//
// All non-demo, headline numbers backed by regulator/aggregator primitives.
// We do NOT fake-source the AI-specific modeled inputs elsewhere in the bank;
// we simply lead with the concepts whose numbers are genuinely sourced.
export const FEATURED_CONCEPT_SLUGS = [
  "kyber-pc-doc-gen",
  "effective-ai-insurance-knowledge",
  "doc-gen-pc-insurance",
] as const;

// Resolve the curated allowlist against the live concept list. Allowlisted
// slugs that exist are returned first, in allowlist order; if any are missing
// (a concept was renamed/removed), the list is topped up from the remaining
// concepts so the homepage always shows `count` cards. Deterministic — no
// dependence on background-refetch ordering.
export function selectFeaturedSlugs(
  concepts: ReadonlyArray<{ slug: string }>,
  count = 3,
): string[] {
  const available = new Set(concepts.map((c) => c.slug));
  const picked: string[] = FEATURED_CONCEPT_SLUGS.filter((s) => available.has(s));
  if (picked.length < count) {
    for (const c of concepts) {
      if (picked.length >= count) break;
      if (!picked.includes(c.slug)) picked.push(c.slug);
    }
  }
  return picked.slice(0, count);
}
