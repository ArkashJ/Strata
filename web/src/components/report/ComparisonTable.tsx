"use client";

// ComparisonTable — the "named players, side-by-side" archetype from the design
// refs: a category column, an optional brand-logo slot, a horizontal magnitude
// bar, a formatted value, and (optionally) a per-row note. Paired with an
// "insight card" rail that states the takeaway in editorial voice.
//
// This is the competitive-landscape block: named competitors with shares/sizes.
// Colour is a single accent voice (a competitor is not a source tier). The logo
// slot is a render-prop so the app can plug simple-icons / favicons without this
// component knowing about brands.

import { useReducedMotion } from "motion/react";
import type * as React from "react";

export interface ComparisonRow {
  key: string;
  label: string;
  value: number;
  display?: string;
  note?: string;
  // Accent override per row (kept in the cool/accent family by callers).
  color?: string;
}

export interface InsightCard {
  // Editorial one-liner takeaway.
  title: string;
  body?: string;
}

export function ComparisonTable({
  rows,
  max,
  headline,
  subtitle,
  source,
  insight,
  renderLogo,
  className,
}: {
  rows: ComparisonRow[];
  max?: number;
  headline?: string;
  subtitle?: string;
  source?: string | null;
  insight?: InsightCard;
  // Optional brand-logo slot, keyed by row.key. Returns null to omit.
  renderLogo?: (row: ComparisonRow) => React.ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion() ?? false;
  const top = max ?? Math.max(...rows.map((r) => r.value), 1);

  if (rows.length === 0) {
    return (
      <div className={`text-[13px] text-[var(--fg-3)] ${className ?? ""}`}>
        No competitors to compare yet.
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

      <div className="grid gap-4 md:grid-cols-[1fr_minmax(0,0.42fr)]">
        <div className="flex flex-col">
          {rows.map((r, i) => {
            const widthPct = Math.max(0, Math.min(100, (r.value / top) * 100));
            const logo = renderLogo?.(r);
            return (
              <div
                key={r.key}
                className="grid grid-cols-[minmax(0,1fr)_2fr_auto] items-center gap-3 border-b border-[var(--border-1)] py-2.5 last:border-0"
              >
                <div className="flex min-w-0 items-center gap-2">
                  {logo ? (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                      {logo}
                    </span>
                  ) : null}
                  <div className="min-w-0">
                    <div className="truncate text-[13px] text-[var(--fg-1)]" title={r.label}>
                      {r.label}
                    </div>
                    {r.note ? (
                      <div className="truncate text-[11px] text-[var(--fg-3)]">{r.note}</div>
                    ) : null}
                  </div>
                </div>
                <div className="h-3.5 overflow-hidden rounded-[var(--r-1)] bg-[var(--bg-3)]">
                  <div
                    className="h-full rounded-[var(--r-1)]"
                    style={{
                      width: `${widthPct}%`,
                      background: r.color ?? "var(--accent)",
                      transition: reduce ? undefined : "width 600ms ease-out",
                      transitionDelay: reduce ? undefined : `${i * 30}ms`,
                    }}
                  />
                </div>
                <span className="tabular-nums text-right text-[13px] text-[var(--fg-1)]">
                  {r.display ?? r.value.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>

        {insight ? (
          <aside className="canvas-card flex flex-col justify-center p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--fg-3)]">
              Insight
            </div>
            <div className="mt-1.5 text-[14px] font-medium leading-snug text-[var(--fg-1)]">
              {insight.title}
            </div>
            {insight.body ? (
              <p className="mt-2 text-[12px] leading-relaxed text-[var(--fg-3)]">{insight.body}</p>
            ) : null}
          </aside>
        ) : null}
      </div>

      {source ? (
        <div className="mt-3 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}
