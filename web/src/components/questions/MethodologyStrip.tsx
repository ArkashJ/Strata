"use client";

// The methodology dashboard, as a row of editorial stat callouts (the Coatue
// "key metric" treatment): how many independent method families agree, how
// independent they are, how tightly they converge, and how many scenarios the
// tree resolves to. These are the trust signals a reader uses to decide how
// much weight the headline TAM can bear. Every value is TAM-field synthesis;
// any metric the concept doesn't resolve is simply omitted.
//
// App-specific by design: depends on the app design tokens + tabular Geist Mono.

import { type MethodMetrics, formatRatio } from "@/lib/report-metrics";

interface Stat {
  label: string;
  value: string;
  hint?: string;
  meter?: number; // 0..1 — draws a thin fill under the value
}

export function MethodologyStrip({
  method,
  className,
}: {
  method: MethodMetrics;
  className?: string;
}) {
  const stats: Stat[] = [];
  if (method.families != null) {
    stats.push({
      label: "Method families",
      value: String(method.families),
      hint: method.families >= 2 ? "triangulated" : "single-method",
    });
  }
  if (method.independence != null) {
    stats.push({
      label: "Independence",
      value: method.independence.toFixed(2),
      hint: "less shared input ↑",
      meter: Math.min(1, Math.max(0, method.independence)),
    });
  }
  if (method.convergenceRatio != null) {
    stats.push({
      label: "Convergence",
      value: formatRatio(method.convergenceRatio),
      hint:
        method.convergenceRatio <= 2 ? "tight" : method.convergenceRatio <= 5 ? "broad" : "wide",
    });
  }
  if (method.scenarios != null) {
    stats.push({ label: "Scenarios", value: String(method.scenarios), hint: "in the tree" });
  }
  if (stats.length === 0) return null;

  return (
    <div
      className={`grid gap-3 ${className ?? ""}`}
      style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0,1fr))` }}
    >
      {stats.map((s) => (
        <div key={s.label} className="canvas-card p-3.5">
          <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
            {s.label}
          </div>
          <div className="display mt-1 text-[22px] leading-none tabular-nums text-[var(--fg-1)]">
            {s.value}
          </div>
          {s.meter != null ? (
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-[var(--bg-2)]">
              <div
                className="h-full rounded-full bg-[var(--accent)]"
                style={{ width: `${s.meter * 100}%` }}
              />
            </div>
          ) : null}
          {s.hint ? <div className="mt-1.5 text-[10px] text-[var(--fg-4)]">{s.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}
