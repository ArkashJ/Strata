"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { type Scenario, formatUSD } from "@/lib/api";

const ROLE_COLORS: Record<string, string> = {
  base_value: "#5b5bd6",
  growth_index: "#3fa66b",
  regime_modifier: "#c99846",
  conditional_adjustment: "#d97849",
};

interface Props {
  scenario: Scenario;
}

export function WaterfallChart({ scenario }: Props) {
  const inputs = scenario.inputs_used;

  interface WaterfallEntry {
    name: string;
    fullName: string;
    value: number;
    displayValue: string;
    role: string;
    unit: string;
  }

  const data: WaterfallEntry[] = inputs.map((input) => {
    const isPercent = input.value < 1 && input.role === "conditional_adjustment";
    return {
      name:
        input.primitive_name.length > 22
          ? `${input.primitive_name.slice(0, 20)}…`
          : input.primitive_name,
      fullName: input.primitive_name,
      value: input.value,
      displayValue: isPercent ? `${(input.value * 100).toFixed(0)}%` : formatCompact(input.value),
      role: input.role,
      unit: input.unit_label,
    };
  });

  data.push({
    name: "= TAM",
    fullName: `${scenario.framework_name} TAM`,
    value: scenario.value,
    displayValue: formatUSD(scenario.value),
    role: "result",
    unit: scenario.unit_label,
  });

  return (
    <div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: "var(--fg-3)" }}
            axisLine={{ stroke: "var(--border-1)" }}
            tickLine={false}
            interval={0}
            angle={-15}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tickFormatter={(v: number) => formatCompact(v)}
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
                    {d.displayValue}
                  </div>
                  <div className="text-[11px] text-[var(--fg-3)] mt-0.5">
                    {d.role.replace(/_/g, " ")} · {d.unit}
                  </div>
                </div>
              );
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={64}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={
                  entry.role === "result"
                    ? "var(--fg-1)"
                    : (ROLE_COLORS[entry.role] ?? "var(--accent)")
                }
                opacity={entry.role === "result" ? 0.85 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 mt-3 text-[11px] text-[var(--fg-3)]">
        <span className="font-medium text-[var(--fg-2)]">Formula:</span>
        {inputs.map((input, i) => (
          <span key={input.primitive_slug}>
            {i > 0 && <span className="mx-1">×</span>}
            <span className="font-mono">{formatCompact(input.value)}</span>
            <span className="ml-0.5 text-[var(--fg-4)]">{input.unit_label}</span>
          </span>
        ))}
        <span className="mx-1">=</span>
        <span className="font-mono font-medium text-[var(--fg-1)]">
          {formatUSD(scenario.value)}
        </span>
      </div>
    </div>
  );
}

function formatCompact(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  if (value < 1) return `${(value * 100).toFixed(0)}%`;
  return value.toLocaleString();
}
