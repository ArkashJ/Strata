// Dependency-free fuzzy ranker for the command palette + interpretation
// matching. Not a full fuzzy-finder — a small, predictable scorer: exact and
// prefix matches win, contiguous substrings beat scattered subsequences, and
// earlier matches beat later ones. Returns only items that match at all.

export interface Scored<T> {
  item: T;
  score: number;
}

// Score a single haystack against the query. Higher is better; 0 means no
// match. Scoring tiers (so ranking is stable and explainable):
//   1000  exact equality
//    800  haystack starts with query
//    600  query appears as a contiguous substring (earlier = higher)
//    1–400 every query char appears in order (subsequence), denser = higher
function scoreOne(haystack: string, query: string): number {
  if (query.length === 0) return 1;
  const h = haystack.toLowerCase();
  const q = query.toLowerCase();

  if (h === q) return 1000;
  if (h.startsWith(q)) return 800;

  const idx = h.indexOf(q);
  if (idx !== -1) {
    // Contiguous substring — reward earlier position.
    return 600 - Math.min(idx, 199);
  }

  // Subsequence: every query char in order. Reward tight clustering and an
  // early first match; bail if any char is missing.
  let hi = 0;
  let firstMatch = -1;
  let lastMatch = -1;
  let matched = 0;
  for (const ch of q) {
    const found = h.indexOf(ch, hi);
    if (found === -1) return 0;
    if (firstMatch === -1) firstMatch = found;
    lastMatch = found;
    hi = found + 1;
    matched++;
  }
  if (matched < q.length) return 0;
  const span = lastMatch - firstMatch + 1;
  const density = q.length / span; // 1.0 == perfectly contiguous
  return Math.round(1 + 399 * density - Math.min(firstMatch, 100));
}

// Rank `items` by how well `keyFn(item)` matches `query`, best first.
// Empty query returns every item (score 1) in original order. Ties keep
// original order (stable sort).
export function rankByQuery<T>(
  items: readonly T[],
  query: string,
  keyFn: (item: T) => string,
): Scored<T>[] {
  const trimmed = query.trim();
  const scored = items.map((item, index) => ({
    item,
    score: scoreOne(keyFn(item), trimmed),
    index,
  }));
  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(({ item, score }) => ({ item, score }));
}
