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

import { formatCompact, formatUSD } from "@/lib/format";
import type { InputUsed, Scenario, Unit } from "@/lib/schemas";

const ROLE_COLORS: Record<string, string> = {
  base_value: "#5b5bd6",
  growth_index: "#3fa66b",
  regime_modifier: "#c99846",
  conditional_adjustment: "#d97849",
};

interface Props {
  scenario: Scenario;
}

function inputLabel(input: InputUsed): string {
  return input.name ?? input.primitive_slug.replace(/-/g, " ");
}

function unitSuffix(unit: Unit | null | undefined): string {
  if (!unit) return "";
  return unit.denominator ? `/${unit.denominator}` : (unit.kind ?? "");
}

export function WaterfallChart({ scenario }: Props) {
  // Evaluator may leave inputs unenriched (value null); chart only the bars it can size.
  const inputs = scenario.inputs_used.filter((i) => i.value != null);

  interface WaterfallEntry {
    name: string;
    fullName: string;
    value: number;
    displayValue: string;
    role: string;
    unit: string;
  }

  const data: WaterfallEntry[] = inputs.map((input) => {
    const value = input.value ?? 0;
    const full = inputLabel(input);
    return {
      name: full.length > 22 ? `${full.slice(0, 20)}…` : full,
      fullName: full,
      value,
      displayValue: formatCompact(value, input.unit),
      role: input.role,
      unit: unitSuffix(input.unit),
    };
  });

  data.push({
    name: "= TAM",
    fullName: `${scenario.definition} TAM`,
    value: scenario.value,
    displayValue: formatCompact(scenario.value, scenario.unit),
    role: "result",
    unit: unitSuffix(scenario.unit),
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
                    {d.role.replace(/_/g, " ")}
                    {d.unit && ` · ${d.unit}`}
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
            <span className="font-mono">{formatCompact(input.value ?? 0, input.unit)}</span>
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
