"use client";

// KpiStrip — the executive figure row at the top of a report (triangulated TAM ·
// range · methods · independence). Props-driven: pass any list of {label, value}
// and optionally mark one as the emphasis figure (rendered in the display face).
// Numbers are tabular-mono. Flat elevation, radius via --r-3.

export interface KpiItem {
  label: string;
  value: string;
  // The headline figure renders larger in the serif display face. At most one.
  emphasis?: boolean;
  // Optional one-word qualifier under the value (e.g. "modeled", "sourced").
  note?: string;
}

export function KpiStrip({ items, className }: { items: KpiItem[]; className?: string }) {
  if (items.length === 0) return null;
  return (
    <div className={`grid grid-cols-2 gap-3 sm:grid-cols-4 ${className ?? ""}`}>
      {items.map((it) => (
        <div key={it.label} className="canvas-card p-4">
          <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
            {it.label}
          </div>
          <div
            className={`mt-1 tabular-nums text-[var(--fg-1)] ${
              it.emphasis ? "display text-[26px] leading-none" : "text-[18px] font-medium"
            }`}
          >
            {it.value}
          </div>
          {it.note ? (
            <div className="mt-1 font-mono text-[10px] uppercase tracking-wide text-[var(--fg-3)]">
              {it.note}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
