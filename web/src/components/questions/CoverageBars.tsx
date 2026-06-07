"use client";

// Coverage by category as a ranked horizontal bar list (the Gartner vendor-score
// pattern), replacing the cramped radar. Each row reads as "answered of total"
// against a muted track, sorted most-covered first — so the reader sees at a
// glance which dimensions the bank can actually defend and which are thin.
// Derived purely from answered/total counts; authors nothing.
//
// App-specific by design: depends on the app design tokens + tabular Geist Mono.

import { CATEGORY_LABEL, type CategoryCoverage } from "@/lib/report-metrics";

export function CoverageBars({
  coverage,
  className,
}: {
  coverage: readonly CategoryCoverage[];
  className?: string;
}) {
  if (coverage.length === 0) return null;
  // Rank by coverage fraction desc, then by volume so ties read sensibly.
  const rows = [...coverage].sort((a, b) => {
    const fa = a.answered / a.total;
    const fb = b.answered / b.total;
    return fb - fa || b.total - a.total;
  });

  return (
    <div className={className}>
      <div className="flex flex-col gap-2.5">
        {rows.map((r) => {
          const pct = Math.round((r.answered / r.total) * 100);
          return (
            <div key={r.category} className="grid grid-cols-[104px_1fr_auto] items-center gap-3">
              <span className="truncate text-[12px] text-[var(--fg-2)]">
                {CATEGORY_LABEL[r.category]}
              </span>
              <div
                className="h-2.5 overflow-hidden rounded-full bg-[var(--bg-2)]"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${CATEGORY_LABEL[r.category]}: ${r.answered} of ${r.total} answered`}
              >
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-[width]"
                  style={{ width: `${pct}%` }}
                  aria-hidden="true"
                />
              </div>
              <span className="font-mono text-[11px] tabular-nums text-[var(--fg-3)]">
                {r.answered}/{r.total}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
