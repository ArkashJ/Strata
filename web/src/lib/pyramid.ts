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

// The three axes share the accent + two tier hues so the eye reads
// qualitative/quantitative/industry at a glance (brand-kit §1.7). The renderer
// strokes each node in its pillar color; logic stays color-agnostic.
export const PILLAR_COLOR: Record<Pillar, string> = {
  qualitative: "var(--fg-2)",
  quantitative: "var(--accent)",
  industry: "var(--tier-analyst)",
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

// A selection holds zero-or-more keys per pillar. A plain click collapses a
// pillar to a single choice; shift-click ORs additional choices into the
// pillar (Q11 "Shift-click → OR within pillar"). An empty/absent array means
// the pillar is unconstrained.
export type Selection = Partial<Record<Pillar, string[]>>;

// The active keys for a pillar, normalized to an array (absent → []).
function selected(sel: Selection, pillar: Pillar): string[] {
  return sel[pillar] ?? [];
}

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
 * Frameworks compatible with the current selection. Within a pillar the chosen
 * keys are OR'd (shift-click); across pillars they are AND'd. A framework
 * survives iff:
 *   - any selected lens equals framework.lens (or no lens is selected), AND
 *   - any selected method family equals framework.method_family (or none), AND
 *   - the framework's lens is the primary lens of some selected industry (or
 *     no industry is selected).
 * With no selection, every framework is compatible.
 */
export function compatibleFrameworks(p: Pyramid, sel: Selection): FrameworkSummary[] {
  const lenses = selected(sel, "qualitative");
  const mfs = selected(sel, "quantitative");
  const industryLenses = selected(sel, "industry")
    .map((slug) => p.concepts.find((c) => c.slug === slug)?.primary_lens)
    .filter((l): l is string => Boolean(l));

  return p.frameworks.filter((f) => {
    if (lenses.length > 0 && !lenses.includes(f.lens)) return false;
    if (mfs.length > 0 && !mfs.includes(f.method_family)) return false;
    if (industryLenses.length > 0 && !industryLenses.includes(f.lens)) return false;
    return true;
  });
}

/**
 * Whether a node is greyed out (incompatible) under the current selection.
 *
 * Rules:
 *   - When a pillar has any selection, its selected nodes stay active and the
 *     un-selected siblings grey out (the pillar has narrowed to those choices).
 *   - A cross-pillar node greys out when no compatible framework (under the
 *     rest of the selection) is reachable through it.
 *   - Industry nodes additionally require their primary lens to match one of
 *     the selected lenses.
 */
export function isGreyed(p: Pyramid, sel: Selection, node: PyramidNode): boolean {
  const selectedInPillar = selected(sel, node.pillar);
  if (selectedInPillar.length > 0) {
    return !selectedInPillar.includes(node.key);
  }

  // No selection in this node's pillar — test reachability against the rest of
  // the selection by pretending this node were the sole choice for its pillar.
  const probe: Selection = { ...sel, [node.pillar]: [node.key] };
  if (node.pillar === "industry") {
    // Industry must also be lens-coherent: if a lens is selected, the concept's
    // primary lens must match one of the selected lenses.
    const lenses = selected(sel, "qualitative");
    const conceptLens = p.concepts.find((c) => c.slug === node.key)?.primary_lens;
    if (lenses.length > 0 && conceptLens && !lenses.includes(conceptLens)) return true;
  }
  return compatibleFrameworks(p, probe).length === 0;
}

/**
 * Toggle a node into/out of the selection.
 *   - Plain click ({ additive: false }) replaces the pillar's choice with this
 *     one; clicking the sole active node clears the pillar.
 *   - Shift-click ({ additive: true }) ORs this node into the pillar (Q11);
 *     re-shift-clicking an active node removes just that one.
 */
export function narrow(
  sel: Selection,
  node: PyramidNode,
  opts: { additive?: boolean } = {},
): Selection {
  const next: Selection = { ...sel };
  const current = selected(next, node.pillar);
  const isActive = current.includes(node.key);

  if (opts.additive) {
    const widened = isActive ? current.filter((k) => k !== node.key) : [...current, node.key];
    if (widened.length === 0) delete next[node.pillar];
    else next[node.pillar] = widened;
    return next;
  }

  // Plain click: a sole active node toggles off; otherwise collapse to this one.
  if (isActive && current.length === 1) delete next[node.pillar];
  else next[node.pillar] = [node.key];
  return next;
}
