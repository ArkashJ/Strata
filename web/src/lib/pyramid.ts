// Pure derivation + compatibility logic for the read-only pyramid graph
// renderer. No React, no network — everything here is deterministic so it can
// be unit-tested in isolation. The renderer (PyramidGraph) and page
// (/graph) consume `buildPyramid` + `narrow` and never recompute topology.
//
// The pyramid has three pillars (the locked U1 axes):
//   Qualitative  — the six analysis lenses (concept.primary_lens / framework.lens)
//   Quantitative — method families (framework.method_family)
//   Industry     — concepts (verticals), keyed by concept slug
//
// Frameworks are the join object that ties a lens to a method family; concepts
// tie an industry to its primary lens. Selecting one node narrows the graph by
// greying every sibling/cross-pillar node that is no longer reachable.

import type { ConceptSummary, FrameworkSummary, PrimitiveSummary } from "./schemas";

export type Pillar = "qualitative" | "quantitative" | "industry";

export const PILLARS: readonly Pillar[] = ["qualitative", "quantitative", "industry"] as const;

export const PILLAR_LABEL: Record<Pillar, string> = {
  qualitative: "Qualitative",
  quantitative: "Quantitative",
  industry: "Industry",
};

export interface PyramidNode {
  id: string;
  pillar: Pillar;
  // The raw registry key this node maps to (lens value, method_family value,
  // or concept slug). Used for compatibility joins.
  key: string;
  label: string;
  // How many registry records sit behind this node (frameworks for a lens /
  // method family, primitives for a concept). Surfaced as a count badge.
  weight: number;
}

export interface Pyramid {
  nodes: PyramidNode[];
  concepts: ConceptSummary[];
  frameworks: FrameworkSummary[];
  primitives: PrimitiveSummary[];
}

// A selection is at most one node per pillar (click-to-narrow collapses a
// pillar to a single choice; clicking the active node clears it).
export type Selection = Partial<Record<Pillar, string>>;

function humanize(raw: string): string {
  return raw
    .split(/[_-]/)
    .filter(Boolean)
    .map((s) => (s[0]?.toUpperCase() ?? "") + s.slice(1))
    .join(" ");
}

function conceptName(concepts: ConceptSummary[], slug: string): string {
  return concepts.find((c) => c.slug === slug)?.name ?? humanize(slug);
}

/**
 * Derive the pyramid topology from the three list endpoints. Nodes are sorted
 * deterministically (by weight desc, then key) so the layout is stable across
 * renders and the tests can assert on order.
 */
export function buildPyramid(
  concepts: ConceptSummary[],
  frameworks: FrameworkSummary[],
  primitives: PrimitiveSummary[],
): Pyramid {
  const lensWeight = new Map<string, number>();
  const mfWeight = new Map<string, number>();

  for (const f of frameworks) {
    if (f.lens) lensWeight.set(f.lens, (lensWeight.get(f.lens) ?? 0) + 1);
    if (f.method_family) mfWeight.set(f.method_family, (mfWeight.get(f.method_family) ?? 0) + 1);
  }
  // Concepts contribute their primary lens even when no framework references it
  // yet, so the qualitative axis is never silently empty.
  for (const c of concepts) {
    if (c.primary_lens && !lensWeight.has(c.primary_lens)) lensWeight.set(c.primary_lens, 0);
  }

  const primitiveCountByConcept = new Map<string, number>();
  for (const p of primitives) {
    if (!p.concept_slug) continue;
    primitiveCountByConcept.set(
      p.concept_slug,
      (primitiveCountByConcept.get(p.concept_slug) ?? 0) + 1,
    );
  }

  const qualitative: PyramidNode[] = [...lensWeight.entries()].map(([key, weight]) => ({
    id: `qualitative:${key}`,
    pillar: "qualitative" as const,
    key,
    label: humanize(key),
    weight,
  }));

  const quantitative: PyramidNode[] = [...mfWeight.entries()].map(([key, weight]) => ({
    id: `quantitative:${key}`,
    pillar: "quantitative" as const,
    key,
    label: humanize(key),
    weight,
  }));

  const industry: PyramidNode[] = concepts.map((c) => ({
    id: `industry:${c.slug}`,
    pillar: "industry" as const,
    key: c.slug,
    label: c.name || conceptName(concepts, c.slug),
    weight: primitiveCountByConcept.get(c.slug) ?? c.measurement_count ?? 0,
  }));

  const byWeightThenKey = (a: PyramidNode, b: PyramidNode) =>
    b.weight - a.weight || a.key.localeCompare(b.key);

  return {
    nodes: [
      ...qualitative.sort(byWeightThenKey),
      ...quantitative.sort(byWeightThenKey),
      ...industry.sort(byWeightThenKey),
    ],
    concepts,
    frameworks,
    primitives,
  };
}

/**
 * Frameworks compatible with the current selection. A framework survives iff:
 *   - the selected lens (if any) equals framework.lens, AND
 *   - the selected method family (if any) equals framework.method_family, AND
 *   - the selected industry (if any) shares that concept's primary lens.
 * With no selection, every framework is compatible.
 */
export function compatibleFrameworks(p: Pyramid, sel: Selection): FrameworkSummary[] {
  const lens = sel.qualitative;
  const mf = sel.quantitative;
  const industrySlug = sel.industry;
  const industryLens = industrySlug
    ? p.concepts.find((c) => c.slug === industrySlug)?.primary_lens
    : undefined;

  return p.frameworks.filter((f) => {
    if (lens && f.lens !== lens) return false;
    if (mf && f.method_family !== mf) return false;
    if (industryLens && f.lens !== industryLens) return false;
    return true;
  });
}

/**
 * Whether a node is greyed out (incompatible) under the current selection.
 *
 * Rules:
 *   - A pillar's own selected node is always active; its un-selected siblings
 *     grey out (the pillar has narrowed to one choice).
 *   - A cross-pillar node greys out when no compatible framework (under the
 *     rest of the selection) is reachable through it.
 *   - Industry nodes additionally require their primary lens to match a
 *     selected lens.
 */
export function isGreyed(p: Pyramid, sel: Selection, node: PyramidNode): boolean {
  const selectedInPillar = sel[node.pillar];
  if (selectedInPillar !== undefined) {
    return node.key !== selectedInPillar;
  }

  // No selection in this node's pillar — test reachability against the rest of
  // the selection by pretending this node were the choice for its pillar.
  const probe: Selection = { ...sel, [node.pillar]: node.key };
  if (node.pillar === "industry") {
    // Industry must also be lens-coherent: if a lens is selected, the concept's
    // primary lens must match it.
    const lens = sel.qualitative;
    const conceptLens = p.concepts.find((c) => c.slug === node.key)?.primary_lens;
    if (lens && conceptLens && conceptLens !== lens) return true;
  }
  return compatibleFrameworks(p, probe).length === 0;
}

/**
 * Toggle a node into/out of the selection. Selecting a node in a pillar
 * replaces any prior choice in that pillar; clicking the active node clears it.
 */
export function narrow(sel: Selection, node: PyramidNode): Selection {
  const next: Selection = { ...sel };
  if (next[node.pillar] === node.key) {
    delete next[node.pillar];
  } else {
    next[node.pillar] = node.key;
  }
  return next;
}
