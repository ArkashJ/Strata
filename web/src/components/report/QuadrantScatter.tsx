"use client";

// QuadrantScatter — the Gartner "Magic Quadrant" archetype: a 2x2 plane with
// labelled axes and quadrant captions, points placed by (x, y) in 0–1 space and
// labelled inline. Built on recharts ScatterChart so the axes/grid come for
// free; quadrant captions + dividing lines are drawn as reference elements.
//
// Points are the accent voice (a positioned player is neither a source tier nor
// a method). Reduced-motion gates the entrance.

import { useReducedMotion } from "motion/react";
import {
  CartesianGrid,
  LabelList,
  ReferenceLine,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import { ChartContainer } from "@/components/ui/chart";

export interface QuadrantPoint {
  label: string;
  // Both in 0–1 space; the chart fixes the domain so callers normalise first.
  x: number;
  y: number;
}

export function QuadrantScatter({
  points,
  xLabel,
  yLabel,
  quadrantLabels,
  headline,
  subtitle,
  source,
  className,
}: {
  points: QuadrantPoint[];
  xLabel: string;
  yLabel: string;
  // [bottomLeft, bottomRight, topLeft, topRight] captions, e.g.
  // ["Niche", "Challengers", "Visionaries", "Leaders"].
  quadrantLabels?: [string, string, string, string];
  headline: string;
  subtitle?: string;
  source?: string | null;
  className?: string;
}) {
  const reduce = useReducedMotion() ?? false;

  if (points.length === 0) {
    return (
      <ChartFrame title={headline} subtitle={subtitle} source={source} className={className}>
        <div className="py-10 text-center text-[13px] text-[var(--fg-3)]">
          No players positioned yet.
        </div>
      </ChartFrame>
    );
  }

  const labels = quadrantLabels;

  return (
    <ChartFrame
      title={headline}
      subtitle={subtitle}
      source={source}
      axisCaption={`x: ${xLabel} · y: ${yLabel} (0–1 normalised)`}
      className={className}
    >
      <ChartContainer config={{}} className="aspect-square w-full max-w-[440px]">
        <ScatterChart margin={{ top: 24, right: 24, bottom: 24, left: 24 }}>
          <CartesianGrid stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            domain={[0, 1]}
            tickCount={3}
            tick={{ fontSize: 10, fill: "var(--fg-3)" }}
            axisLine={{ stroke: "var(--border-2)" }}
            tickLine={false}
            label={{ value: xLabel, position: "bottom", fontSize: 11, fill: "var(--fg-3)" }}
          />
          <YAxis
            type="number"
            dataKey="y"
            domain={[0, 1]}
            tickCount={3}
            tick={{ fontSize: 10, fill: "var(--fg-3)" }}
            axisLine={{ stroke: "var(--border-2)" }}
            tickLine={false}
            label={{
              value: yLabel,
              angle: -90,
              position: "left",
              fontSize: 11,
              fill: "var(--fg-3)",
            }}
          />
          <ZAxis range={[120, 120]} />
          <ReferenceLine x={0.5} stroke="var(--border-2)" />
          <ReferenceLine y={0.5} stroke="var(--border-2)" />
          {labels ? (
            <>
              <ReferenceLine
                x={0.02}
                y={0.02}
                stroke="transparent"
                label={{
                  value: labels[0],
                  position: "insideBottomLeft",
                  fontSize: 9,
                  fill: "var(--fg-4)",
                }}
              />
              <ReferenceLine
                x={0.98}
                y={0.02}
                stroke="transparent"
                label={{
                  value: labels[1],
                  position: "insideBottomRight",
                  fontSize: 9,
                  fill: "var(--fg-4)",
                }}
              />
              <ReferenceLine
                x={0.02}
                y={0.98}
                stroke="transparent"
                label={{
                  value: labels[2],
                  position: "insideTopLeft",
                  fontSize: 9,
                  fill: "var(--fg-4)",
                }}
              />
              <ReferenceLine
                x={0.98}
                y={0.98}
                stroke="transparent"
                label={{
                  value: labels[3],
                  position: "insideTopRight",
                  fontSize: 9,
                  fill: "var(--fg-4)",
                }}
              />
            </>
          ) : null}
          <Scatter data={points} fill="var(--accent)" isAnimationActive={!reduce}>
            <LabelList
              dataKey="label"
              position="top"
              style={{ fontSize: 10, fill: "var(--fg-1)" }}
            />
          </Scatter>
        </ScatterChart>
      </ChartContainer>
    </ChartFrame>
  );
}
