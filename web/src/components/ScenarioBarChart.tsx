"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { type Scenario, formatUSD } from "@/lib/api";

const METHOD_COLORS: Record<string, string> = {
  bottoms_up_seats: "#5b5bd6",
  top_down_spend: "#3fa66b",
  analog_penetration: "#c99846",
  comparable_revenue: "#2ba39a",
  value_chain: "#8b5cd6",
};

interface Props {
  scenarios: Scenario[];
}

export function ScenarioBarChart({ scenarios }: Props) {
  const data = scenarios.map((s) => ({
    name: s.framework_name.length > 28 ? `${s.framework_name.slice(0, 25)}…` : s.framework_name,
    value: s.value,
    method: s.method_family,
    fullName: s.framework_name,
  }));

  const avg = scenarios.reduce((sum, s) => sum + s.value, 0) / scenarios.length;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 11, fill: "var(--fg-3)" }}
          axisLine={{ stroke: "var(--border-1)" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v: number) => formatUSD(v)}
          tick={{ fontSize: 11, fill: "var(--fg-3)" }}
          axisLine={false}
          tickLine={false}
          width={72}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.[0]) return null;
            const d = payload[0].payload as (typeof data)[number];
            return (
              <div className="canvas-card px-3 py-2" style={{ borderRadius: "var(--r-2)" }}>
                <div className="text-[12px] text-[var(--fg-1)] font-medium">{d.fullName}</div>
                <div className="tam-num text-[16px] text-[var(--fg-1)] mt-1">
                  {formatUSD(d.value)}
                </div>
                <div className="text-[11px] text-[var(--fg-3)] mt-0.5">
                  {d.method.replace(/_/g, " ")}
                </div>
              </div>
            );
          }}
        />
        <ReferenceLine
          y={avg}
          stroke="var(--fg-4)"
          strokeDasharray="6 4"
          label={{
            value: `avg ${formatUSD(avg)}`,
            position: "right",
            fontSize: 11,
            fill: "var(--fg-3)",
          }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={80}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={METHOD_COLORS[entry.method] ?? "var(--accent)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
