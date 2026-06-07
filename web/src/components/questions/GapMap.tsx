"use client";

// The coverage matrix — every applicable question as one cell, grouped by
// category, filled when answered and hollow-dashed when it's a gap. The point
// is to make the bank's THINNESS legible: a reader sees instantly that e.g.
// segmentation and unit-economics are mostly hollow, and the footer names what
// the next ingest would fill. Honesty made spatial — gaps aren't hidden in
// prose, they're the empty cells you can count.
//
// App-specific by design: depends on the app design tokens.

import { CATEGORY_LABEL, CATEGORY_ORDER, type CategoryCoverage } from "@/lib/report-metrics";
import type { QuestionCategory } from "@/lib/schemas";

interface GapTarget {
  category: QuestionCategory;
  resourceTarget: string | null;
}

export function GapMap({
  coverage,
  gapTargets,
  className,
}: {
  coverage: readonly CategoryCoverage[];
  gapTargets: readonly GapTarget[];
  className?: string;
}) {
  if (coverage.length === 0) return null;
  const byCat = new Map(coverage.map((c) => [c.category, c]));
  const rows = CATEGORY_ORDER.filter((c) => byCat.has(c));

  // One descriptor per question cell, with a pre-made stable id, so the render
  // maps over `cell.id` (not a bare array index — keeps the key lint happy).
  const cellsFor = (cat: QuestionCategory, answered: number, gaps: number) => [
    ...Array.from({ length: answered }, (_, i) => ({ id: `${cat}-a-${i}`, answered: true })),
    ...Array.from({ length: gaps }, (_, i) => ({ id: `${cat}-g-${i}`, answered: false })),
  ];

  // The distinct connectors the open gaps would draw from — the "what's next".
  const targets = [
    ...new Set(gapTargets.map((g) => g.resourceTarget).filter((t): t is string => t != null)),
  ];

  return (
    <div className={className}>
      <div className="flex flex-col gap-2">
        {rows.map((cat) => {
          const c = byCat.get(cat) as CategoryCoverage;
          const gaps = c.total - c.answered;
          return (
            <div key={cat} className="grid grid-cols-[104px_1fr] items-center gap-3">
              <span className="truncate text-[12px] text-[var(--fg-2)]">{CATEGORY_LABEL[cat]}</span>
              <div className="flex flex-wrap gap-1">
                {/* Fixed-length decorative cells, one per question. */}
                {cellsFor(cat, c.answered, gaps).map((cell) => (
                  <span
                    key={cell.id}
                    className={
                      cell.answered
                        ? "h-3 w-3 rounded-[3px] bg-[var(--accent)]"
                        : "h-3 w-3 rounded-[3px] border border-dashed border-[var(--fg-4)]"
                    }
                    title={cell.answered ? "answered" : "gap — no sourced figure"}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend + what-fills-the-gaps */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-[var(--border-1)] pt-3 text-[10px] text-[var(--fg-3)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-[var(--accent)]" /> answered
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] border border-dashed border-[var(--fg-4)]" /> gap
        </span>
      </div>
      {targets.length > 0 ? (
        <p className="mt-2 text-[10px] leading-relaxed text-[var(--fg-4)]">
          Gaps would be sourced from:{" "}
          {targets.slice(0, 8).map((t, i) => (
            <span key={t}>
              {i > 0 ? " · " : ""}
              <span className="font-mono text-[var(--fg-3)]">{t}</span>
            </span>
          ))}
          {targets.length > 8 ? ` · +${targets.length - 8} more` : ""}
        </p>
      ) : null}
    </div>
  );
}
