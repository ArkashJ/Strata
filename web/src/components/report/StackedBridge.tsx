"use client";

// StackedBridge — the "how the inputs build to the TAM" waterfall. Each step is
// one factor in the multiplicative chain (population × adoption × WTP → TAM),
// drawn as a labelled segment with the running product, ending in the TAM bar.
//
// Steps are coloured by INPUT PROVENANCE (tier ramp) — the bridge's job is to
// show which factors are well-sourced and which are modeled, so the tier ramp
// (not a lens hue) is the correct meaning here. The final TAM bar is the accent
// voice. A pure horizontal flow, flat fills, no gradient.

import { tierColor } from "@/lib/chart-colors";

export interface BridgeStep {
  label: string;
  // The factor value (e.g. 12_000_000 population, 0.3 adoption).
  factor: number;
  // Pre-formatted display of the factor (e.g. "12.0M", "30%").
  display: string;
  tier?: string | null;
}

export function StackedBridge({
  steps,
  total,
  totalLabel = "TAM",
  totalDisplay,
  headline,
  subtitle,
  source,
  className,
}: {
  steps: BridgeStep[];
  total: number;
  totalLabel?: string;
  totalDisplay: string;
  headline?: string;
  subtitle?: string;
  source?: string | null;
  className?: string;
}) {
  if (steps.length === 0) {
    return (
      <div className={`text-[13px] text-[var(--fg-3)] ${className ?? ""}`}>
        No factor chain for this method.
      </div>
    );
  }

  return (
    <figure className={className}>
      {headline ? (
        <figcaption className="mb-3">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
            {headline}
          </div>
          {subtitle ? (
            <div className="mt-0.5 text-[12px] text-[var(--fg-3)]">{subtitle}</div>
          ) : null}
        </figcaption>
      ) : null}

      {/* The factor flow: each step → × → next, ending in = TAM. */}
      <div className="flex flex-wrap items-stretch gap-2">
        {steps.map((s, i) => (
          <div key={s.label} className="flex items-stretch gap-2">
            <div
              className="flex min-w-[96px] flex-col rounded-[var(--r-2)] border-l-[3px] bg-[var(--bg-2)] px-3 py-2"
              style={{ borderColor: tierColor(s.tier) }}
            >
              <span className="truncate text-[11px] text-[var(--fg-3)]" title={s.label}>
                {s.label}
              </span>
              <span className="tabular-nums text-[16px] font-medium text-[var(--fg-1)]">
                {s.display}
              </span>
            </div>
            <span className="self-center text-[16px] text-[var(--fg-4)]">
              {i < steps.length - 1 ? "×" : "="}
            </span>
          </div>
        ))}
        <div className="flex min-w-[120px] flex-col rounded-[var(--r-2)] border border-[var(--accent)] bg-[var(--accent-tint)] px-3 py-2">
          <span className="font-mono text-[10px] uppercase tracking-wide text-[var(--accent)]">
            {totalLabel}
          </span>
          <span className="tam-num text-[18px] text-[var(--fg-1)]">{totalDisplay}</span>
        </div>
      </div>

      {/* Magnitude bridge bars — the running contribution of each step toward
          the total, so the eye sees which factor is doing the work. */}
      <div className="mt-4 flex h-2.5 overflow-hidden rounded-[var(--r-round)] bg-[var(--bg-3)]">
        {steps.map((s) => {
          // Each step's share of the (log-spread) factor magnitudes, normalised
          // so the bar reads as relative weight, never an absolute claim.
          const weight = Math.max(0, Math.log10(Math.abs(s.factor) + 1));
          const totalWeight =
            steps.reduce((acc, st) => acc + Math.max(0, Math.log10(Math.abs(st.factor) + 1)), 0) ||
            1;
          return (
            <div
              key={s.label}
              style={{
                width: `${(weight / totalWeight) * 100}%`,
                background: tierColor(s.tier),
              }}
              title={`${s.label}: ${s.display}`}
            />
          );
        })}
      </div>
      <div className="mt-1 text-right tabular-nums text-[11px] text-[var(--fg-3)]">
        product → {totalDisplay} ({total.toExponential(1)})
      </div>

      {source ? (
        <div className="mt-3 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}
