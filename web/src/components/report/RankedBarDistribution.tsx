"use client";

// RankedBarDistribution — the Gartner "Vendors' Product Scores" archetype: a
// ranked list of named rows, each a horizontal bar to its score, with the
// value pinned at the bar's end and zebra row striping. Sorted desc by default
// so the leader sits on top.
//
// Colour is a single accent voice (a ranking is not provenance and not method).
// An optional `tier` per row tints the bar by source tier when the ranking IS
// provenance-bearing (caller opts in via `colorBy="tier"`).

import { useReducedMotion } from "motion/react";

import { tierColor } from "@/lib/chart-colors";

export interface RankedRow {
  label: string;
  value: number;
  // Optional formatted value override (e.g. "3.95" or "$1.2B"). Falls back to
  // a fixed-2 number.
  display?: string;
  // Source tier, used only when colorBy="tier".
  tier?: string | null;
}

export function RankedBarDistribution({
  rows,
  max,
  headline,
  subtitle,
  source,
  colorBy = "accent",
  sort = true,
  className,
}: {
  rows: RankedRow[];
  // Axis maximum; defaults to the largest value.
  max?: number;
  headline?: string;
  subtitle?: string;
  source?: string | null;
  // "accent" = single editorial voice (default); "tier" = provenance ramp.
  colorBy?: "accent" | "tier";
  sort?: boolean;
  className?: string;
}) {
  const reduce = useReducedMotion() ?? false;
  const ordered = sort ? [...rows].sort((a, b) => b.value - a.value) : rows;
  const top = max ?? Math.max(...rows.map((r) => r.value), 1);

  if (rows.length === 0) {
    return (
      <div className={`text-[13px] text-[var(--fg-3)] ${className ?? ""}`}>
        No rows to rank yet.
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

      <div className="flex flex-col">
        {ordered.map((r, i) => {
          const widthPct = Math.max(0, Math.min(100, (r.value / top) * 100));
          const fill = colorBy === "tier" ? tierColor(r.tier) : "var(--accent)";
          return (
            <div
              key={r.label}
              className="grid grid-cols-[minmax(0,1fr)_2.5fr_auto] items-center gap-3 border-b border-[var(--border-1)] py-2 last:border-0"
            >
              <span className="truncate text-[13px] text-[var(--fg-1)]" title={r.label}>
                {r.label}
              </span>
              <div className="h-3.5 overflow-hidden rounded-[var(--r-1)] bg-[var(--bg-3)]">
                <div
                  className="h-full rounded-[var(--r-1)]"
                  style={{
                    width: `${widthPct}%`,
                    background: fill,
                    transition: reduce ? undefined : "width 600ms ease-out",
                    transitionDelay: reduce ? undefined : `${i * 30}ms`,
                  }}
                />
              </div>
              <span className="tabular-nums text-right text-[13px] text-[var(--fg-1)]">
                {r.display ?? r.value.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>

      {source ? (
        <div className="mt-3 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}
