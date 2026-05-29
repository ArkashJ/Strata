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

import { formatUSD, lensLabel } from "@/lib/format";
import type { Scenario } from "@/lib/schemas";

// Lens drives the colour here: the real Scenario carries no method_family, so we
// key off the analysis lens the framework declares (matches FrameworkCard chips).
const LENS_COLORS: Record<string, string> = {
  cost_efficiency: "#5b5bd6",
  revenue_generation: "#3fa66b",
  latent_demand: "#c99846",
  platform_throughput: "#2ba39a",
  bundle_consolidation: "#d97849",
  productivity_uplift: "#8b5cd6",
};

interface Props {
  scenarios: Scenario[];
}

export function ScenarioBarChart({ scenarios }: Props) {
  const data = scenarios.map((s) => ({
    name: s.definition.length > 28 ? `${s.definition.slice(0, 25)}…` : s.definition,
    value: s.value,
    lens: s.lens,
    fullName: s.definition,
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
                <div className="text-[11px] text-[var(--fg-3)] mt-0.5">{lensLabel(d.lens)}</div>
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
            <Cell key={entry.name} fill={LENS_COLORS[entry.lens] ?? "var(--accent)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
