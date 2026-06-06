"use client";

// GARTNER CHART CONTRACT — a thin composition wrapper layered ON TOP OF the
// shadcn ChartContainer (ui/chart.tsx), never a rewrite of it. It supplies the
// four Gartner-grade elements the design contract names, so a bar length is
// never read as a literal number divorced from its axis, unit, and source:
//
//   1. TITLE / SUBTITLE / SOURCE-FOOTNOTE frame  (editorial mono caps title)
//   2. AXIS TITLE + UNIT caption                 (the hidden numeric axis,
//                                                  captioned so log/swing scales
//                                                  aren't misread)
//   3. slot for ON-CHART ANNOTATIONS/CALLOUTS    (children pass ReferenceLine)
//   4. COLOR-MEANS-ONE-THING                      (enforced via chart-colors.ts
//                                                  helpers at the call sites)
//
// This wrapper is APP-SCOPED on purpose (NOT a portable/standalone component):
// it lives in the app and depends on the app tokens (--fg-*/--tier-*/
// --chart-lens-*) by design — that token dependency is the whole point of the
// colour contract, so it is deliberately not the reusable kind.
//
// The source footnote is honesty-fenced: when the caller can't compose a REAL
// source string it passes `source={null}` and the footnote renders nothing. We
// never fabricate "source: …" (mirrors TamReport's leansOnModeled fence).

import { useReducedMotion } from "motion/react";
import type * as React from "react";

import { tierLabel } from "@/lib/format";

interface ChartFrameProps {
  // Editorial title — mono uppercase, matches TamReport's SectionTitle.
  title: string;
  // Optional one-line context under the title.
  subtitle?: string;
  // Pinned source footnote, e.g. "source: BLS OEWS, 2024". Pass null/undefined
  // to render NOTHING (no fabricated provenance). Prefer composing it via
  // `sourceFootnote()` below so the honesty fence is centralised.
  source?: string | null;
  // Axis caption — the unit/scale of the (hidden) value axis, e.g.
  // "USD nominal, log scale" or "TAM swing ±20%". Rendered in --fg-3.
  axisCaption?: string;
  className?: string;
  // Render-prop OR plain children. The function form receives the resolved
  // reduced-motion flag so the chart can gate recharts `isAnimationActive`.
  children: React.ReactNode | ((ctx: { reduceMotion: boolean }) => React.ReactNode);
}

export function ChartFrame({
  title,
  subtitle,
  source,
  axisCaption,
  className,
  children,
}: ChartFrameProps) {
  // `useReducedMotion` returns boolean | null (null before hydration); coerce so
  // the default is "animate" once known, "don't animate" when the user opts out.
  const reduceMotion = useReducedMotion() ?? false;
  const body = typeof children === "function" ? children({ reduceMotion }) : children;

  return (
    <figure className={className}>
      {/* 1. TITLE / SUBTITLE frame */}
      <figcaption className="mb-2">
        <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
          {title}
        </div>
        {subtitle ? <div className="mt-0.5 text-[12px] text-[var(--fg-3)]">{subtitle}</div> : null}
      </figcaption>

      {body}

      {/* 2. AXIS TITLE + UNIT caption — the hidden numeric axis, named so the
          bar lengths aren't read as literal values. */}
      {axisCaption ? (
        <div className="mt-1.5 text-[10px] text-[var(--fg-3)]">{axisCaption}</div>
      ) : null}

      {/* 1. SOURCE FOOTNOTE — honesty-fenced: only renders when real. */}
      {source ? (
        <div className="mt-2 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}

// Compose a "source: <Tier>, <year>" footnote string from a provenance row,
// honesty-fenced: returns null when there's no real tier (composite inputs,
// modeled rows) so ChartFrame renders nothing rather than a fabricated source.
export function sourceFootnote(
  iu: { source_tier?: string | null; as_of?: string | null } | null | undefined,
): string | null {
  if (!iu?.source_tier) return null;
  const year = iu.as_of ? new Date(iu.as_of).getFullYear() : null;
  const tier = tierLabel(iu.source_tier);
  return year && !Number.isNaN(year) ? `source: ${tier}, ${year}` : `source: ${tier}`;
}
