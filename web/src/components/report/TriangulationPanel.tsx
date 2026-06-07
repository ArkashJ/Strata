"use client";

// TriangulationPanel — the #1 credibility marker of a $1M report made visual:
// the same market sized two independent ways (top-down ∧ bottom-up), the gap
// between them shown and named. A thin wrapper that prefers the existing
// ConvergenceBanner (when the backend supplies a `convergence` object) and
// otherwise states the missing direction plainly — it NEVER fabricates a second
// method to fill the panel.
//
// Method markers wear the LENS family (these are methods, not sources). When no
// convergence is present, the panel shows the single sized method and an honest
// "second method not yet sourced" note.

import { ConvergenceBanner } from "@/components/charts/ConvergenceBanner";
import { familyLabel, formatCompact } from "@/lib/format";
import type { Convergence, Unit } from "@/lib/schemas";

export interface SingleMethod {
  family: string;
  value: number;
  unit: Unit;
}

export function TriangulationPanel({
  convergence,
  singleMethod,
  headline = "Triangulation",
  className,
}: {
  // When present, the full top-down vs bottom-up cross-check renders.
  convergence?: Convergence | null;
  // Fallback when only one method sized the concept — shown honestly.
  singleMethod?: SingleMethod | null;
  headline?: string;
  className?: string;
}) {
  if (convergence) {
    return (
      <section className={className}>
        <ConvergenceBanner convergence={convergence} />
      </section>
    );
  }

  return (
    <section className={`canvas-card p-6 ${className ?? ""}`}>
      <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">{headline}</div>
      {singleMethod ? (
        <>
          <div className="mt-3 flex items-baseline gap-2.5">
            <span className="tam-num text-[40px] leading-none text-[var(--fg-1)]">
              {formatCompact(singleMethod.value, singleMethod.unit)}
            </span>
            <span className="text-[13px] text-[var(--fg-3)]">
              {familyLabel(singleMethod.family)}
            </span>
          </div>
          <p className="mt-4 text-[12px] leading-relaxed text-[var(--fg-3)]">
            Only one independent method sized this market so far. A second direction (the
            counterpart top-down or bottoms-up estimate) is not yet sourced — so there is no
            cross-check to show. We state this plainly rather than manufacture a second method.
          </p>
        </>
      ) : (
        <p className="mt-3 text-[12px] leading-relaxed text-[var(--fg-3)]">
          No triangulation available for this TAM.
        </p>
      )}
    </section>
  );
}
