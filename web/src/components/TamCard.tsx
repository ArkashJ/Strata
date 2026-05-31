/**
 * TamCard — row card for a recently-updated TAM artifact.
 * Links to /tam/<hash> (read-only artifact page, landing in PR7).
 */

"use client";

import { useRouter } from "next/navigation";

import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { formatUSD } from "@/lib/format";

export interface TamSummary {
  state_hash: string;
  concept_name: string;
  /** Low-end scenario value in USD */
  low: number;
  /** High-end scenario value in USD */
  high: number;
  /** ISO date string — used to render relative recency */
  created_at: string;
  lens: string;
  /** 0–1 method-independence score — drives the defensibility ring */
  independence_score?: number;
  /** distinct method families that triangulate this TAM (≥2 = triangulated) */
  method_families?: number;
}

function relativeDate(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

interface TamCardProps {
  tam: TamSummary;
  /**
   * Where the card navigates. Defaults to the frozen artifact page
   * /tam/<hash>, which is now durable (TAMs persist to Postgres, P0.1), so the
   * permalink resolves across restarts. Override only for special routing.
   */
  href?: string;
}

// A defensible TAM (≥2 independent method families) must LOOK different from a
// single-method guess — this is the visual that separates Strata from an LLM
// spitting out one number. Triangulated → green; single-method → muted.
function MethodBadge({ count }: { count: number }) {
  const triangulated = count >= 2;
  return (
    <span
      className="shrink-0 rounded-[var(--r-1)] px-1.5 py-0.5 text-[10px] font-medium tabular-nums"
      style={{
        color: triangulated ? "var(--tier-regulator)" : "var(--fg-4)",
        backgroundColor: triangulated ? "var(--tier-regulator-tint)" : "var(--bg-2)",
      }}
      title={
        triangulated
          ? `Triangulated across ${count} independent method families`
          : "Single method family — not yet triangulated"
      }
    >
      {triangulated ? `△ ${count} methods` : "single method"}
    </span>
  );
}

export function TamCard({ tam, href }: TamCardProps) {
  const router = useRouter();
  const hasDefensibility = tam.independence_score != null && tam.method_families != null;

  return (
    <button
      type="button"
      onClick={() => router.push(href ?? `/tam/${tam.state_hash}`)}
      className="canvas-card group w-full text-left px-4 py-3 flex items-center gap-3
                 cursor-pointer hover:translate-y-[-1px] active:translate-y-0
                 transition-transform duration-[var(--t-fast)]"
    >
      {hasDefensibility ? (
        <IndependenceDonut score={tam.independence_score ?? 0} size={30} strokeWidth={4} showLabel={false} />
      ) : null}
      <span className="flex-1 text-[13px] font-medium text-[var(--fg-1)] truncate">
        {tam.concept_name}
      </span>
      {hasDefensibility ? <MethodBadge count={tam.method_families ?? 0} /> : null}
      <span className="shrink-0 text-[12px] text-[var(--fg-2)] tabular-nums">
        {formatUSD(tam.low)}
        <span className="text-[var(--fg-4)] mx-1">–</span>
        {formatUSD(tam.high)}
      </span>
      <span className="shrink-0 text-[11px] text-[var(--fg-4)] w-[60px] text-right">
        {relativeDate(tam.created_at)}
      </span>
    </button>
  );
}
