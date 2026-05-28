/**
 * TierSparkline — compact horizontal bar showing source-tier distribution.
 * Used in ConceptCard footers to give a quick credibility signal without
 * opening the detail page.
 */

import type { SourceTier } from "@/lib/schemas";

interface TierCount {
  tier: SourceTier;
  count: number;
}

interface TierSparklineProps {
  tiers: TierCount[];
  className?: string;
}

// Maps each tier to its CSS variable so bars inherit the brand palette.
const TIER_VAR: Record<string, string> = {
  regulator: "var(--tier-regulator)",
  aggregator: "var(--tier-aggregator)",
  analyst: "var(--tier-analyst)",
  "analyst-paraphrase": "var(--tier-analyst)",
  community: "var(--tier-community)",
  "community-modeled": "var(--tier-community)",
  onchain: "var(--tier-onchain)",
  prediction_market: "var(--tier-prediction)",
  first_party: "var(--tier-first-party)",
};

export function TierSparkline({ tiers, className = "" }: TierSparklineProps) {
  const total = tiers.reduce((s, t) => s + t.count, 0);
  if (total === 0) return null;

  return (
    <div
      role="img"
      aria-label={`Source tier distribution: ${tiers.map((t) => `${t.tier} ${t.count}`).join(", ")}`}
      className={`flex h-[4px] w-full overflow-hidden rounded-[var(--r-round)] gap-px ${className}`}
    >
      {tiers.map(({ tier, count }) => (
        <span
          key={tier}
          style={{
            width: `${(count / total) * 100}%`,
            background: TIER_VAR[tier] ?? "var(--tier-community)",
          }}
          className="shrink-0"
        />
      ))}
    </div>
  );
}
