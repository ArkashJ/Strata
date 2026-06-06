// The "a colour means ONE thing" contract, made callable.
//
//   TIER RAMP   = PROVENANCE only  → tierColor()  → --tier-* (warm/earth hues)
//   COOL FAMILY = LENS (method) only → lensColor() → --chart-lens-* (cool family)
//
// These two ramps are deliberately disjoint in globals.css; routing every chart
// fill through these helpers (instead of inline hex) keeps the meaning from
// crossing — a method can never wear a source-tier hue, and vice versa. A
// palette change propagates from one place (the :root tokens) to every chart.

// Source-tier → provenance colour. Returns a CSS var string so it tracks the
// light/dark toggle. Unknown / null tier → community (neutral grey), never a
// lens hue.
const TIER_VARS: Record<string, string> = {
  regulator: "var(--tier-regulator)",
  aggregator: "var(--tier-aggregator)",
  analyst: "var(--tier-analyst)",
  community: "var(--tier-community)",
  "community-modeled": "var(--tier-community)",
  onchain: "var(--tier-onchain)",
  prediction_market: "var(--tier-prediction)",
  first_party: "var(--tier-first-party)",
  "first-party": "var(--tier-first-party)",
};

export function tierColor(tier: string | null | undefined): string {
  if (!tier) return "var(--tier-community)";
  return TIER_VARS[tier] ?? "var(--tier-community)";
}

// Lens (method) → cool-family colour. Returns a CSS var string. Unknown / null
// lens → the indigo accent (still cool family), never a tier hue.
const LENS_VARS: Record<string, string> = {
  cost_efficiency: "var(--chart-lens-cost-efficiency)",
  revenue_generation: "var(--chart-lens-revenue-generation)",
  latent_demand: "var(--chart-lens-latent-demand)",
  platform_throughput: "var(--chart-lens-platform-throughput)",
  bundle_consolidation: "var(--chart-lens-bundle-consolidation)",
  productivity_uplift: "var(--chart-lens-productivity-uplift)",
};

export function lensColor(lens: string | null | undefined): string {
  if (!lens) return "var(--accent)";
  return LENS_VARS[lens] ?? "var(--accent)";
}
