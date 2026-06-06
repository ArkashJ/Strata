"use client";

// Radial bar — concentric arcs, one per row. AGNOSTIC: recharts only, no app
// tokens/classes. Best for a small set (≤6) of parts-of-a-whole readings.
import { RadialBar, RadialBarChart, ResponsiveContainer, Tooltip } from "recharts";

export interface RadialDatum {
  label: string;
  value: number;
  fill?: string;
}

export const DEFAULT_PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function RadialChart({
  data,
  colors = DEFAULT_PALETTE,
  height = 240,
}: {
  data: RadialDatum[];
  colors?: string[];
  height?: number;
}) {
  if (data.length === 0) return null;

  const rows = data.map((d, i) => ({ ...d, fill: d.fill ?? colors[i % colors.length] }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadialBarChart data={rows} innerRadius="30%" outerRadius="100%" startAngle={90} endAngle={-270}>
        <Tooltip />
        <RadialBar dataKey="value" background cornerRadius={6} />
      </RadialBarChart>
    </ResponsiveContainer>
  );
}
