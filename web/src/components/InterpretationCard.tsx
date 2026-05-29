/**
 * InterpretationCard — shown on /?q= to let the user pick which interpretation
 * of their query to size. Each card maps a fuzzy match to a known concept and
 * shows scope (narrow/broad/default) plus a preview range.
 */

"use client";

import { useRouter } from "next/navigation";

import { formatUSD } from "@/lib/format";
import type { ConceptSummary } from "@/lib/schemas";

const SCOPE_LABEL: Record<string, string> = {
  narrow: "Narrower",
  broad: "Broader",
  default: "Best match",
};
const SCOPE_CLASS: Record<string, string> = {
  narrow: "bg-[var(--accent-tint)] text-[var(--accent-active)]",
  broad: "bg-[rgba(201,152,70,0.14)] text-[var(--tier-analyst)]",
  default: "bg-[rgba(63,166,107,0.14)] text-[var(--tier-regulator)]",
};

export interface InterpretationMatch {
  concept: ConceptSummary;
  scope: "narrow" | "broad" | "default";
  previewRange: { low: number; high: number } | null;
  score: number;
}

interface InterpretationCardProps {
  match: InterpretationMatch;
}

export function InterpretationCard({ match }: InterpretationCardProps) {
  const router = useRouter();
  const { concept, scope, previewRange } = match;

  return (
    <button
      type="button"
      onClick={() => router.push(`/build?q=${encodeURIComponent(concept.name)}`)}
      className="canvas-card group w-full text-left p-5 flex flex-col gap-3
                 cursor-pointer hover:translate-y-[-1px] active:translate-y-0
                 transition-transform duration-[var(--t-fast)]"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[14px] font-medium text-[var(--fg-1)] leading-[1.3]">
          {concept.name}
        </span>
        <span className={`role-chip shrink-0 ${SCOPE_CLASS[scope] ?? SCOPE_CLASS.default}`}>
          {SCOPE_LABEL[scope] ?? "Match"}
        </span>
      </div>

      <p className="text-[12px] text-[var(--fg-3)] leading-[1.45] line-clamp-2">
        {concept.definition}
      </p>

      <div className="flex items-center gap-3 flex-wrap">
        {previewRange && (
          <span className="tam-num text-[13px] text-[var(--fg-1)]">
            {formatUSD(previewRange.low)}
            <span className="text-[var(--fg-4)] mx-1">–</span>
            {formatUSD(previewRange.high)}
          </span>
        )}
        <span className="text-[11px] text-[var(--fg-4)]">
          {concept.measurement_count} primitive{concept.measurement_count !== 1 ? "s" : ""}
        </span>
        <span className="ml-auto text-[11px] text-[var(--accent)] font-medium group-hover:underline">
          Size this →
        </span>
      </div>
    </button>
  );
}
