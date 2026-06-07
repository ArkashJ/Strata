"use client";

// MarketAreaChart — the Coatue "market cap as % of GDP" archetype: a single
// filled area over time with optional annotated peaks (the "34%" / "77%"
// callouts). A flat tinted fill (NO gradient — design contract bans gradient
// fills), the line in the accent voice, dotted peak callouts.
//
// One series, one meaning: this is a magnitude-over-time, so it uses the accent
// (single editorial voice), not a tier/lens ramp. Peaks are passed explicitly
// so the chart never invents a callout.

import { useReducedMotion } from "motion/react";
import { Area, AreaChart, CartesianGrid, ReferenceDot, XAxis, YAxis } from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";

export interface AreaPoint {
  x: number | string;
  value: number;
}

export interface AreaPeak {
  x: number | string;
  // The display label for the callout (e.g. "77%"). Caller formats it so the
  // chart never guesses the unit.
  label: string;
}

export function MarketAreaChart({
  data,
  valueLabel,
  peaks = [],
  headline,
  subtitle,
  source,
  yTickFormat = (v) => String(v),
  className,
}: {
  data: AreaPoint[];
  valueLabel: string;
  peaks?: AreaPeak[];
  headline: string;
  subtitle?: string;
  source?: string | null;
  yTickFormat?: (v: number) => string;
  className?: string;
}) {
  const reduce = useReducedMotion() ?? false;

  if (data.length === 0) {
    return (
      <ChartFrame title={headline} subtitle={subtitle} source={source} className={className}>
        <div className="py-10 text-center text-[13px] text-[var(--fg-3)]">No series data yet.</div>
      </ChartFrame>
    );
  }

  const config: ChartConfig = { value: { label: valueLabel, color: "var(--accent)" } };
  const byX = new Map(data.map((d) => [d.x, d.value]));

  return (
    <ChartFrame title={headline} subtitle={subtitle} source={source} className={className}>
      <ChartContainer config={config} className="aspect-[16/9] w-full">
        <AreaChart data={data} margin={{ top: 16, right: 24, bottom: 8, left: 4 }}>
          <CartesianGrid vertical={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            tickLine={false}
            axisLine={{ stroke: "var(--border-2)" }}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
            tickMargin={8}
          />
          <YAxis
            tickFormatter={yTickFormat}
            tickLine={false}
            axisLine={false}
            width={44}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
          />
          <ChartTooltip
            cursor={{ stroke: "var(--border-2)" }}
            content={<ChartTooltipContent labelKey="x" />}
          />
          {/* Flat fill — explicit fillOpacity, no <linearGradient>. */}
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--accent)"
            strokeWidth={2.5}
            fill="var(--accent)"
            fillOpacity={0.1}
            isAnimationActive={!reduce}
          />
          {peaks.map((p) => {
            const y = byX.get(p.x);
            if (y == null) return null;
            return (
              <ReferenceDot
                key={String(p.x)}
                x={p.x}
                y={y}
                r={5}
                fill="var(--accent)"
                stroke="var(--bg-1)"
                strokeWidth={2}
                label={{
                  value: p.label,
                  position: "top",
                  fontSize: 12,
                  fontWeight: 700,
                  fill: "var(--accent)",
                }}
              />
            );
          })}
        </AreaChart>
      </ChartContainer>
    </ChartFrame>
  );
}
