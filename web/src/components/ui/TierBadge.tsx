/**
 * TierBadge — source-tier pill. A solid dot in the tier color over a tinted
 * background with an uppercase label. Tier color is load-bearing (docs/03):
 * regulator green, aggregator teal, analyst amber, etc. Reads brand tokens
 * `--tier-<key>` / `--tier-<key>-tint` only — no hardcoded hex.
 */

import { tierLabel } from "@/lib/format";
import type { SourceTier } from "@/lib/schemas";

// Map a backend tier onto the CSS-variable key defined in globals.css. Some
// tiers fold onto another's palette (paraphrase → analyst) and the underscore
// variants become hyphenated to match the token names.
const TIER_KEY: Record<SourceTier, string> = {
  first_party: "first-party",
  regulator: "regulator",
  aggregator: "aggregator",
  analyst: "analyst",
  "analyst-paraphrase": "analyst",
  community: "community",
  onchain: "onchain",
  prediction_market: "prediction",
  // No dedicated token — borrow the community palette for modeled sliders.
  "community-modeled": "community",
};

export interface TierBadgeProps {
  tier: SourceTier;
  className?: string;
}

export function TierBadge({ tier, className = "" }: TierBadgeProps) {
  const key = TIER_KEY[tier] ?? "community";
  const dot = `var(--tier-${key})`;
  const tint = `var(--tier-${key}-tint)`;
  return (
    <span
      data-tier={tier}
      className={`inline-flex items-center gap-1.5 rounded-[var(--r-1)] px-2 py-0.5 font-medium text-[10px] uppercase tracking-wide ${className}`}
      style={{ background: tint, color: dot }}
    >
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: dot }}
      />
      {tierLabel(tier)}
    </span>
  );
}
