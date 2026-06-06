"use client";

import type { ChartConfig } from "@/components/ui/chart";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { formatCompact } from "@/lib/format";
// Sensitivity tornado (Wave 2 / AC2.3) — one floating horizontal bar per input,
// spanning its ±pct low→high TAM swing, sorted by |impact| so the most
// load-bearing assumption sits on top. Fed by GET /build/{slug}/sensitivity.
//
// The data prep (`toTornadoData`) is a pure function so the sort contract is
// unit-testable without rendering recharts.
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

export interface SensitivityRow {
  primitive_slug: string;
  name: string;
  base: number;
  low: number;
  high: number;
  impact: number;
}

export interface SensitivityResponse {
  concept_slug: string;
  base: number;
  pct: number;
  inputs: SensitivityRow[];
}

export interface TornadoDatum {
  slug: string;
  label: string;
  lo: number;
  hi: number;
  base: number;
  impact: number;
  // Floating-bar [start, end] so recharts draws low→high.
  range: [number, number];
}

function truncate(s: string, max = 26): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

// Sort by |impact| desc (defensive — the API already sorts) and normalise the
// low/high ordering so `range` is always [min, max].
export function toTornadoData(resp: SensitivityResponse): TornadoDatum[] {
  return [...resp.inputs]
    .sort((a, b) => b.impact - a.impact)
    .map((r) => {
      const lo = Math.min(r.low, r.high);
      const hi = Math.max(r.low, r.high);
      return {
        slug: r.primitive_slug,
        label: truncate(r.name),
        lo,
        hi,
        base: r.base,
        impact: r.impact,
        range: [lo, hi] as [number, number],
      };
    });
}

export function TornadoChart({ data }: { data: SensitivityResponse }) {
  const rows = toTornadoData(data);
  if (rows.length === 0) {
    return (
      <div className="text-[13px] text-[var(--fg-3)]">No perturbable inputs for this TAM.</div>
    );
  }

  const config: ChartConfig = { range: { label: "TAM swing" } };
  const height = Math.min(Math.max(rows.length * 40, 120), 480);
  const pctLabel = `±${Math.round(data.pct * 100)}%`;

  // Encode |impact| as accent intensity (one hue, never a second color): the
  // most load-bearing assumption is full indigo, lesser ones fade via opacity
  // so the eye ranks them before reading a single label. Opacity (not a
  // color-mix string) because recharts paints this as an SVG fill attribute.
  const maxImpact = Math.max(...rows.map((r) => Math.abs(r.impact)), 1);
  const barOpacity = (impact: number) => 0.45 + 0.55 * (Math.abs(impact) / maxImpact);

  return (
    <div>
      <ChartContainer config={config} className="aspect-auto w-full" style={{ height }}>
        <BarChart accessibilityLayer data={rows} layout="vertical" margin={{ left: 8, right: 64 }}>
          <CartesianGrid horizontal={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="hi" hide domain={["dataMin", "dataMax"]} />
          <YAxis
            type="category"
            dataKey="label"
            width={170}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 13, fill: "var(--fg-2)" }}
          />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                hideIndicator
                labelKey="label"
                formatter={(_v, _n, item) => {
                  const d = item.payload as TornadoDatum;
                  return (
                    <div className="flex flex-col">
                      <span className="text-[12px] font-medium text-[var(--fg-1)]">{d.label}</span>
                      <span className="tam-num text-[13px] text-[var(--fg-1)]">
                        {formatCompact(d.lo)} – {formatCompact(d.hi)}
                      </span>
                      <span className="text-[11px] text-[var(--fg-3)]">
                        impact {formatCompact(d.impact)} · {pctLabel}
                      </span>
                    </div>
                  );
                }}
              />
            }
          />
          <Bar dataKey="range" radius={4} maxBarSize={28}>
            {rows.map((d) => (
              <Cell key={d.slug} fill="var(--accent)" fillOpacity={barOpacity(d.impact)} />
            ))}
          </Bar>
        </BarChart>
      </ChartContainer>
      <p className="mt-2 text-[12px] text-[var(--fg-3)]">
        Each bar is the TAM swing when that input moves {pctLabel} · sorted by impact.
      </p>
    </div>
  );
}
