"use client";

// The "disagreement gets a page" chart (Principle #2), made visual. A banker's
// football-field range bar on a LOG axis: the floor (lowest method family), the
// ceiling (floor × the disagreement multiple), and the triangulated midpoint
// that leads the report. The wide spread IS the point — a number you quote
// depends on which method you believe, so we show the whole band, never a lone
// headline. Same-unit ($) by construction; mixed-unit measurements never enter
// here (they live in the source ledger instead).
//
// App-specific by design: depends on the app design tokens + tabular Geist Mono.

import { ChartFrame } from "@/components/charts/ChartFrame";
import { formatUSD } from "@/lib/format";
import { type RangeMetrics, formatRatio } from "@/lib/report-metrics";

// Compact label for a decade gridline (always a power of ten): "$100M", "$1B".
function decadeLabel(v: number): string {
  if (v >= 1e9) return `$${Math.round(v / 1e9)}B`;
  if (v >= 1e6) return `$${Math.round(v / 1e6)}M`;
  if (v >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${v}`;
}

// Log position [0,1] of `v` within [min,max]. Clamped so a marker just outside
// the gridline range still renders on the track.
function logPos(v: number, min: number, max: number): number {
  const lo = Math.log10(min);
  const hi = Math.log10(max);
  if (hi <= lo) return 0;
  return Math.min(1, Math.max(0, (Math.log10(v) - lo) / (hi - lo)));
}

// Pick "nice" decade gridlines that bracket the range, e.g. 100M · 1B · 10B.
function decadeTicks(min: number, max: number): number[] {
  const lo = Math.floor(Math.log10(min));
  const hi = Math.ceil(Math.log10(max));
  const ticks: number[] = [];
  for (let e = lo; e <= hi; e++) ticks.push(10 ** e);
  return ticks;
}

export function TamRangeField({
  range,
  headlineDisplay,
  className,
}: {
  range: RangeMetrics;
  headlineDisplay?: string | null;
  className?: string;
}) {
  const { low, high, mid, spreadRatio } = range;
  // Pad the axis a third of a decade on each side so the end bars aren't flush
  // against the track edge.
  const axisMin = 10 ** (Math.log10(low) - 0.33);
  const axisMax = 10 ** (Math.log10(high) + 0.33);
  const ticks = decadeTicks(axisMin, axisMax);

  const lowPct = logPos(low, axisMin, axisMax) * 100;
  const highPct = logPos(high, axisMin, axisMax) * 100;
  const midPct = mid != null ? logPos(mid, axisMin, axisMax) * 100 : null;
  // Pre-format the midpoint label so the JSX needs no non-null assertion.
  const midLabel = mid != null ? (headlineDisplay ?? formatUSD(mid)) : null;

  const subtitle =
    spreadRatio != null
      ? `Floor ${formatUSD(low)} → ceiling ${formatUSD(high)} · ${formatRatio(spreadRatio)} spread`
      : `Floor ${formatUSD(low)} → ceiling ${formatUSD(high)}`;

  return (
    <ChartFrame
      title="TAM range across methods"
      subtitle={subtitle}
      axisCaption="USD nominal · log scale · band = lowest-to-highest method family"
      source={null}
      className={className}
    >
      <div className="relative mt-6 mb-1 select-none">
        {/* Midpoint callout above the band */}
        {midPct != null ? (
          <div
            className="pointer-events-none absolute -top-5 flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${midPct}%` }}
          >
            <span className="whitespace-nowrap font-mono text-[11px] font-medium tabular-nums text-[var(--accent)]">
              {midLabel}
            </span>
          </div>
        ) : null}

        {/* Track + gridlines */}
        <div className="relative h-11">
          {/* Decade gridlines */}
          {ticks.map((t) => {
            const p = logPos(t, axisMin, axisMax) * 100;
            return (
              <div
                key={t}
                className="absolute top-0 bottom-0 w-px bg-[var(--border-1)]"
                style={{ left: `${p}%` }}
              />
            );
          })}

          {/* The range band (floor → ceiling) */}
          <div
            className="absolute top-1/2 h-3.5 -translate-y-1/2 rounded-full"
            style={{
              left: `${lowPct}%`,
              width: `${highPct - lowPct}%`,
              background:
                "linear-gradient(90deg, var(--accent-tint), color-mix(in srgb, var(--accent) 55%, transparent))",
              border: "1px solid var(--accent-ring)",
            }}
          />

          {/* Floor & ceiling end caps */}
          {[lowPct, highPct].map((p, i) => (
            <div
              key={i === 0 ? "floor" : "ceiling"}
              className="absolute top-1/2 h-5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--accent)]"
              style={{ left: `${p}%` }}
            />
          ))}

          {/* Midpoint marker — the headline figure */}
          {midPct != null ? (
            <div
              className="absolute top-1/2 h-7 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--fg-1)]"
              style={{ left: `${midPct}%` }}
            />
          ) : null}
        </div>

        {/* Axis tick labels */}
        <div className="relative mt-1 h-4">
          {ticks.map((t) => {
            const p = logPos(t, axisMin, axisMax) * 100;
            return (
              <span
                key={t}
                className="absolute -translate-x-1/2 font-mono text-[9px] tabular-nums text-[var(--fg-4)]"
                style={{ left: `${p}%` }}
              >
                {decadeLabel(t)}
              </span>
            );
          })}
        </div>

        {/* Floor / ceiling value labels under their caps */}
        <div className="relative mt-3 h-4">
          <span
            className="absolute -translate-x-1/2 whitespace-nowrap font-mono text-[11px] tabular-nums text-[var(--fg-2)]"
            style={{ left: `${lowPct}%` }}
          >
            {formatUSD(low)}
          </span>
          <span
            className="absolute -translate-x-1/2 whitespace-nowrap font-mono text-[11px] tabular-nums text-[var(--fg-2)]"
            style={{ left: `${highPct}%` }}
          >
            {formatUSD(high)}
          </span>
        </div>
      </div>
    </ChartFrame>
  );
}
