"use client";

// "How do the methods compare" — a horizontal bar across every scenario in the
// current TAMOutput. Each bar is one scenario (one framework/lens reading of the
// market); the length is the computed headline value, formatted via formatCompact.
// Horizontal layout keeps long lens/definition labels readable at any count.
//
// Honesty: scenarios already span a single sourced value each — we never invent a
// range. A single-scenario TAM renders one clear bar (not a fabricated series),
// with a note that only one method is wired so the reader knows the spread is real.
import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import { formatCompact, lensLabel } from "@/lib/format";
import type { Scenario, TAMOutput } from "@/lib/schemas";

// Lens drives the bar colour — matches ScenarioBarChart / ResolveResultChart / chips.
const LENS_COLORS: Record<string, string> = {
  cost_efficiency: "#5b5bd6",
  revenue_generation: "#3fa66b",
  latent_demand: "#c99846",
  platform_throughput: "#2ba39a",
  bundle_consolidation: "#d97849",
  productivity_uplift: "#8b5cd6",
};

interface Datum {
  // Truncated y-axis label.
  label: string;
  full: string;
  lensName: string;
  value: number;
  display: string;
  fill: string;
}

function truncate(s: string, max = 24): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function scenarioLabel(s: Scenario): string {
  // Definition is the human handle; fall back to the framework slug if absent.
  return s.definition?.trim() || s.framework.replace(/-/g, " ");
}

export function ScenarioComparisonChart({ tam }: { tam: TAMOutput }) {
  const scenarios = tam.scenarios;

  if (scenarios.length === 0) {
    return (
      <div className="text-[13px] text-[var(--fg-3)]">No scenarios computed for this TAM yet.</div>
    );
  }

  const unit = scenarios[0].unit;
  const data: Datum[] = scenarios.map((s) => {
    const full = scenarioLabel(s);
    return {
      label: truncate(full),
      full,
      lensName: lensLabel(s.lens),
      value: s.value,
      display: formatCompact(s.value, s.unit),
      fill: LENS_COLORS[s.lens] ?? "var(--accent)",
    };
  });

  const config: ChartConfig = { value: { label: "TAM" } };
  // Bar height scales with count so two scenarios don't render as fat slabs and
  // ten don't crush together; clamp so the card stays a sensible height.
  const height = Math.min(Math.max(scenarios.length * 44, 120), 480);

  return (
    <div>
      <ChartContainer config={config} className="aspect-auto w-full" style={{ height }}>
        <BarChart accessibilityLayer data={data} layout="vertical" margin={{ left: 8, right: 72 }}>
          <CartesianGrid horizontal={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="value" hide />
          <YAxis
            type="category"
            dataKey="label"
            width={160}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
          />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                hideIndicator
                labelKey="full"
                formatter={(_v, _n, item) => {
                  const d = item.payload as Datum;
                  return (
                    <div className="flex flex-col">
                      <span className="text-[12px] font-medium text-[var(--fg-1)]">{d.full}</span>
                      <span className="tam-num text-[14px] text-[var(--fg-1)]">{d.display}</span>
                      <span className="text-[11px] text-[var(--fg-3)]">{d.lensName}</span>
                    </div>
                  );
                }}
              />
            }
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={40}>
            {data.map((d) => (
              <Cell key={d.full} fill={d.fill} />
            ))}
            <LabelList
              dataKey="display"
              position="right"
              className="fill-[var(--fg-2)]"
              fontSize={11}
            />
          </Bar>
        </BarChart>
      </ChartContainer>
      {scenarios.length === 1 ? (
        <p className="mt-2 text-[11px] text-[var(--fg-3)]">
          One method wired for this concept · the spread fills in as competing frameworks attach.
        </p>
      ) : (
        <p className="mt-2 text-[11px] text-[var(--fg-3)]">
          {scenarios.length} methods ·{" "}
          {formatCompact(Math.min(...scenarios.map((s) => s.value)), unit)} –{" "}
          {formatCompact(Math.max(...scenarios.map((s) => s.value)), unit)} spread
        </p>
      )}
    </div>
  );
}
