"use client";

// Donut / pie. AGNOSTIC: depends only on recharts. No app tokens, no app CSS
// classes, no shadcn wrapper — pass data + (optionally) colors and it renders
// anywhere. A donut (innerRadius > 0) leaves room for a center total.
import { Label, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export interface Slice {
  label: string;
  value: number;
  // Optional per-slice override; otherwise cycles through `colors`.
  fill?: string;
}

// Self-contained default palette — works with zero theming. Override via prop.
export const DEFAULT_PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function DonutChart({
  data,
  colors = DEFAULT_PALETTE,
  centerLabel,
  centerValue,
  height = 240,
  // Disable for print/PDF: recharts' entry animation leaves the ring as a
  // partial arc if a snapshot/print is taken before it finishes.
  animate = true,
}: {
  data: Slice[];
  colors?: string[];
  centerLabel?: string;
  centerValue?: string;
  height?: number;
  animate?: boolean;
}) {
  if (data.length === 0) return null;

  const slices = data.map((d, i) => ({ ...d, fill: d.fill ?? colors[i % colors.length] }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Tooltip />
        <Pie
          data={slices}
          dataKey="value"
          nameKey="label"
          innerRadius="58%"
          strokeWidth={2}
          isAnimationActive={animate}
        >
          {centerLabel || centerValue ? (
            <Label
              content={({ viewBox }) => {
                if (!viewBox || !("cx" in viewBox)) return null;
                const { cx, cy } = viewBox;
                return (
                  <text
                    x={cx}
                    y={cy}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="currentColor"
                  >
                    {centerValue ? (
                      <tspan x={cx} y={cy} style={{ fontSize: 22, fontWeight: 600 }}>
                        {centerValue}
                      </tspan>
                    ) : null}
                    {centerLabel ? (
                      <tspan x={cx} y={(cy ?? 0) + 22} style={{ fontSize: 12, opacity: 0.6 }}>
                        {centerLabel}
                      </tspan>
                    ) : null}
                  </text>
                );
              }}
            />
          ) : null}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}
