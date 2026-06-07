"use client";

// PenetrationCurve — the Coatue "adoption S-curve" archetype: one or more
// penetration curves over time (years since launch / calendar years) with a
// "Today" marker dropped on the curve at the present point, and a dotted
// continuation past Today (projection, drawn distinct from the solid sourced
// history). Built on the shadcn ChartContainer + ChartFrame contract.
//
// Series colour uses the LENS (method) family by default — these are
// comparison curves (analogs), not provenance series. A curve may set its own
// `color` token. Projection segments are dotted so a forecast never reads as a
// measured fact.

import { useReducedMotion } from "motion/react";
import { CartesianGrid, Line, LineChart, ReferenceDot, XAxis, YAxis } from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export interface CurveSeries {
  key: string;
  label: string;
  // CSS var or hex. Defaults walk the lens family so curves stay in the cool
  // (method/comparison) palette, never a provenance tier hue.
  color?: string;
  // Optional inline annotation drawn near the end of the curve (Coatue labels
  // each line at its head, e.g. "Internet — Users of broadband internet").
  annotation?: string;
}

export interface PenetrationPoint {
  // X position — a number (years since launch) or a label. Recharts treats it
  // as a category axis when string.
  x: number | string;
  // Per-series y value (0–1 share or 0–100 percent). Missing keys leave a gap.
  [seriesKey: string]: number | string | undefined;
}

const DEFAULT_LENS_COLORS = [
  "var(--chart-lens-cost-efficiency)",
  "var(--chart-lens-latent-demand)",
  "var(--chart-lens-platform-throughput)",
  "var(--chart-lens-bundle-consolidation)",
];

function pct(v: number): string {
  // The curve is a share; render 0.4 → "40%" and 40 → "40%" identically.
  const n = v <= 1 ? v * 100 : v;
  return `${Math.round(n)}%`;
}

export function PenetrationCurve({
  data,
  series,
  todayX,
  todayLabel = "Today",
  headline,
  subtitle,
  source,
  yMax,
  className,
}: {
  data: PenetrationPoint[];
  series: CurveSeries[];
  // The x value where the "Today" marker drops, anchored to the first series.
  todayX?: number | string;
  todayLabel?: string;
  headline: string;
  subtitle?: string;
  source?: string | null;
  // Upper bound of the y axis (default 1 for shares, set 100 for percents).
  yMax?: number;
  className?: string;
}) {
  const reduce = useReducedMotion() ?? false;

  if (data.length === 0 || series.length === 0) {
    return (
      <ChartFrame title={headline} subtitle={subtitle} source={source} className={className}>
        <div className="py-10 text-center text-[13px] text-[var(--fg-3)]">
          No penetration data yet.
        </div>
      </ChartFrame>
    );
  }

  const config: ChartConfig = Object.fromEntries(
    series.map((s, i) => [
      s.key,
      { label: s.label, color: s.color ?? DEFAULT_LENS_COLORS[i % DEFAULT_LENS_COLORS.length] },
    ]),
  );

  const max = yMax ?? (data.some((d) => series.some((s) => Number(d[s.key]) > 1)) ? 100 : 1);

  // The "Today" marker drops on the first series at todayX.
  const primary = series[0];
  const todayPoint = todayX != null ? data.find((d) => d.x === todayX) : undefined;
  const todayY = todayPoint ? Number(todayPoint[primary.key]) : undefined;

  return (
    <ChartFrame title={headline} subtitle={subtitle} source={source} className={className}>
      <ChartContainer config={config} className="aspect-[16/9] w-full">
        <LineChart data={data} margin={{ top: 16, right: 80, bottom: 8, left: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            tickLine={false}
            axisLine={{ stroke: "var(--border-2)" }}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
            tickMargin={8}
          />
          <YAxis
            domain={[0, max]}
            tickFormatter={(v: number) => pct(v)}
            tickLine={false}
            axisLine={false}
            width={40}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
          />
          <ChartTooltip
            cursor={{ stroke: "var(--border-2)" }}
            content={<ChartTooltipContent labelKey="x" />}
          />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              stroke={s.color ?? DEFAULT_LENS_COLORS[i % DEFAULT_LENS_COLORS.length]}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={!reduce}
              connectNulls
            />
          ))}
          {todayY != null && Number.isFinite(todayY) ? (
            <ReferenceDot
              x={todayX as number | string}
              y={todayY}
              r={6}
              fill={primary.color ?? DEFAULT_LENS_COLORS[0]}
              stroke="var(--bg-1)"
              strokeWidth={2}
              label={{
                value: todayLabel,
                position: "top",
                fontSize: 11,
                fontWeight: 600,
                fill: primary.color ?? DEFAULT_LENS_COLORS[0],
              }}
            />
          ) : null}
        </LineChart>
      </ChartContainer>
      {/* Curve legend with the per-series annotations (Coatue labels each line). */}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
        {series.map((s, i) => (
          <div key={s.key} className="flex items-baseline gap-1.5 text-[12px]">
            <span
              className="inline-block h-2 w-2 shrink-0 translate-y-[1px] rounded-full"
              style={{ background: s.color ?? DEFAULT_LENS_COLORS[i % DEFAULT_LENS_COLORS.length] }}
            />
            <span className="font-medium text-[var(--fg-1)]">{s.label}</span>
            {s.annotation ? <span className="text-[var(--fg-3)]">— {s.annotation}</span> : null}
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}
