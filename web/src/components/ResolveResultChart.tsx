"use client";

// The chart shown when a query resolves: the primitives that COMPOSE the TAM,
// drawn as horizontal bars. Inputs span orders of magnitude and different units
// (e.g. 3.0M people x $300/seat = $900M), so the value axis is log-scaled and
// every bar is labelled with its own real value + unit — the bar length is a
// visual cue, the label carries the truth. Wraps shadcn ChartContainer; themed
// to the app's CSS-variable tokens so it tracks the light/dark toggle.
import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from "recharts";

import { ChartFrame, sourceFootnote } from "@/components/charts/ChartFrame";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import { lensColor } from "@/lib/chart-colors";
import { formatCompact, lensLabel } from "@/lib/format";
import type { PrimitiveUsed, ResolverResult } from "@/lib/resolver-schemas";

// Only these lenses are a true product of their inputs (persona × cost, volume ×
// take-rate, …). bundle_consolidation is sum-then-discount, so a "Multiplies to"
// footer would assert false math — show the equation only for genuine products.
const MULTIPLICATIVE_LENSES = new Set([
  "cost_efficiency",
  "revenue_generation",
  "latent_demand",
  "platform_throughput",
  "productivity_uplift",
]);

function unitSuffix(unit: PrimitiveUsed["unit"]): string {
  if (!unit || typeof unit !== "object") return "";
  const u = unit as { denominator?: string | null; dimension?: string | null };
  if (u.denominator) return `/${u.denominator}`;
  return u.dimension ?? "";
}

function primLabel(p: PrimitiveUsed): string {
  return p.name ?? p.slug ?? p.role ?? "input";
}

interface Datum {
  label: string;
  full: string;
  value: number;
  display: string;
  tier: string | null;
}

export function ResolveResultChart({ result }: { result: ResolverResult }) {
  const inputs = result.primitives_used.filter((p) => Number.isFinite(p.value) && p.value > 0);
  if (inputs.length === 0) return null;

  // Lens drives the bar colour — the COOL lens family only (chart-colors.ts),
  // never a source-tier hue. Falls back to the indigo accent (still cool family)
  // when no lens is known.
  const accent = result.lens ? lensColor(result.lens) : "var(--accent)";
  const data: Datum[] = inputs.map((p) => {
    const full = primLabel(p);
    return {
      label: full.length > 22 ? `${full.slice(0, 20)}…` : full,
      full,
      value: p.value,
      display: `${formatCompact(p.value)}${unitSuffix(p.unit) ? ` ${unitSuffix(p.unit)}` : ""}`,
      tier: p.source_tier ?? null,
    };
  });

  // The explicit equation is the whole differentiator over an unsourced LLM
  // answer: show that the TAM is a *product* of these inputs, not a guess. Gated
  // to multiplicative lenses so we never render "A × B" for additive math.
  const showEquation =
    inputs.length >= 2 &&
    result.tam_value != null &&
    result.lens != null &&
    MULTIPLICATIVE_LENSES.has(result.lens);
  const tamLabel =
    result.formatted_tam ?? (result.tam_value != null ? formatCompact(result.tam_value) : "");

  const config: ChartConfig = {
    value: { label: result.lens ? lensLabel(result.lens) : "Value", color: accent },
  };

  // Honesty-fenced source footnote: compose only from a REAL tier carried by an
  // input. Pick the strongest-provenance input present (regulator > aggregator >
  // analyst > …) as the representative source; null → ChartFrame renders nothing.
  const TIER_RANK: Record<string, number> = {
    regulator: 6,
    first_party: 5,
    aggregator: 4,
    analyst: 3,
    prediction_market: 2,
    community: 1,
  };
  const strongest = inputs
    .filter((p) => p.source_tier)
    .sort(
      (a, b) => (TIER_RANK[b.source_tier ?? ""] ?? 0) - (TIER_RANK[a.source_tier ?? ""] ?? 0),
    )[0];
  const source = sourceFootnote(strongest ? { source_tier: strongest.source_tier } : null);

  return (
    <ChartFrame
      className="mt-5 border-t border-[var(--border-1)] pt-4"
      title="How this TAM is built"
      subtitle={
        result.lens ? `${lensLabel(result.lens)} · each factor is a sourced input` : undefined
      }
      axisCaption="Input magnitude, log scale · labels carry the real value + unit"
      source={source}
    >
      <ChartContainer config={config} className="mt-2 aspect-auto h-[240px] w-full">
        <BarChart accessibilityLayer data={data} layout="vertical" margin={{ left: 8, right: 64 }}>
          <CartesianGrid horizontal={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          <XAxis type="number" dataKey="value" scale="log" domain={["auto", "auto"]} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={150}
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
                      {d.tier ? (
                        <span className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
                          {d.tier.replace(/[-_]/g, " ")}
                        </span>
                      ) : null}
                    </div>
                  );
                }}
              />
            }
          />
          <Bar dataKey="value" fill={accent} radius={[0, 4, 4, 0]} maxBarSize={36}>
            <LabelList
              dataKey="display"
              position="right"
              className="fill-[var(--fg-2)]"
              fontSize={11}
            />
          </Bar>
        </BarChart>
      </ChartContainer>
      {showEquation ? (
        // The product line: makes the multiplicative (not additive) relationship
        // explicit — the math a partner can check, the receipt an LLM can't give.
        <div className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] text-[var(--fg-3)]">
          <span className="font-medium text-[var(--fg-2)]">Multiplies to</span>
          {data.map((d, i) => (
            <span key={`${d.full}-${i}`} className="font-mono">
              {i > 0 && <span className="mx-0.5 text-[var(--fg-4)]">×</span>}
              {d.display}
            </span>
          ))}
          <span className="mx-0.5 text-[var(--fg-4)]">=</span>
          <span className="font-mono font-medium text-[var(--fg-1)]">{tamLabel}</span>
        </div>
      ) : null}
    </ChartFrame>
  );
}
