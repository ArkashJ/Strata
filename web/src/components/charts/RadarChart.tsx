"use client";

// Radar / spider — compares one or more series across the SAME axes. AGNOSTIC:
// recharts only, no app tokens/classes. Overlapping polygons make per-axis
// divergence pop.
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart as RechartsRadar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

export const DEFAULT_PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function RadarChart({
  data,
  series,
  colors = DEFAULT_PALETTE,
  height = 260,
  // Disable for print/PDF — see DonutChart.
  animate = true,
}: {
  // One row per axis; each row holds `axis` plus a numeric value per series key.
  data: Array<{ axis: string } & Record<string, string | number>>;
  // The series keys to plot.
  series: string[];
  colors?: string[];
  height?: number;
  animate?: boolean;
}) {
  if (data.length === 0 || series.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsRadar data={data}>
        <Tooltip />
        <PolarGrid />
        <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12, fill: "currentColor" }} />
        {series.map((s, i) => {
          const c = colors[i % colors.length];
          return (
            <Radar
              key={s}
              dataKey={s}
              stroke={c}
              fill={c}
              fillOpacity={0.25}
              strokeWidth={2}
              isAnimationActive={animate}
            />
          );
        })}
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
