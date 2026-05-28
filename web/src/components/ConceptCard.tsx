/**
 * ConceptCard — grid card for a concept summary on the landing page.
 * Clicking navigates to /build?q=<name> so the user arrives at the build
 * workhorse with the concept pre-filled.
 */

"use client";

import { useRouter } from "next/navigation";

import { TierSparkline } from "@/components/ui/TierSparkline";
import { lensLabel } from "@/lib/format";
import type { ConceptSummary, SourceTier } from "@/lib/schemas";

// Deterministic tier distribution derived from measurement_count — a rough
// proxy until the backend exposes per-concept tier breakdowns (v0.4).
function syntheticTiers(count: number): Array<{ tier: SourceTier; count: number }> {
  if (count === 0) return [];
  const reg = Math.max(1, Math.round(count * 0.55));
  const agg = Math.max(0, Math.round(count * 0.25));
  const ana = Math.max(0, count - reg - agg);
  const out: Array<{ tier: SourceTier; count: number }> = [];
  if (reg > 0) out.push({ tier: "regulator", count: reg });
  if (agg > 0) out.push({ tier: "aggregator", count: agg });
  if (ana > 0) out.push({ tier: "analyst", count: ana });
  return out;
}

const LENS_SHORT: Record<string, string> = {
  cost_efficiency: "Cost",
  revenue_generation: "Revenue",
  latent_demand: "Demand",
  platform_throughput: "Throughput",
  bundle_consolidation: "Bundle",
  productivity_uplift: "Productivity",
};

interface ConceptCardProps {
  concept: ConceptSummary;
}

export function ConceptCard({ concept }: ConceptCardProps) {
  const router = useRouter();
  const tiers = syntheticTiers(concept.measurement_count);
  const lensShort = LENS_SHORT[concept.primary_lens] ?? lensLabel(concept.primary_lens);

  return (
    <button
      type="button"
      onClick={() => router.push(`/build?q=${encodeURIComponent(concept.name)}`)}
      className="canvas-card group w-full text-left p-4 flex flex-col gap-3
                 cursor-pointer hover:translate-y-[-1px] active:translate-y-0
                 transition-transform duration-[var(--t-fast)]"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-[13px] font-medium text-[var(--fg-1)] leading-[1.35] line-clamp-2">
          {concept.name}
        </span>
        <span className="role-chip shrink-0">{lensShort}</span>
      </div>

      <p className="text-[12px] text-[var(--fg-3)] leading-[1.45] line-clamp-2 flex-1">
        {concept.definition}
      </p>

      <div className="flex flex-col gap-1.5">
        <span className="text-[11px] text-[var(--fg-4)]">
          {concept.measurement_count} primitive{concept.measurement_count !== 1 ? "s" : ""}
        </span>
        <TierSparkline tiers={tiers} />
      </div>
    </button>
  );
}
