"use client";

// For ONE selected scenario, how its inputs multiply toward the headline value.
// Each bar is one input primitive's own magnitude (people, $/seat, adoption %…) —
// the inputs span orders of magnitude and different units, so the value axis is
// log-scaled and every bar carries its own real value + unit as a label. The bar
// length is a visual cue; the label carries the truth.
//
// This is a MULTIPLICATIVE decomposition, not an additive stack — the inputs do
// not sum to the TAM, they multiply. The footer spells out the product so the
// reader never misreads bar areas as shares.
//
// Honesty: the evaluator may leave inputs unenriched (value null). When no input
// carries a numeric value we render a plain "inputs not enumerated" state rather
// than a fabricated breakdown.
import { Bar, BarChart, CartesianGrid, LabelList, XAxis, YAxis } from "recharts";

import { ChartFrame, sourceFootnote } from "@/components/charts/ChartFrame";
import { SourcedNumber } from "@/components/ui/SourcedNumber";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import { formatCompact } from "@/lib/format";
import type { InputUsed, Scenario, Unit } from "@/lib/schemas";

// Cap the bar count so a many-input scenario doesn't crush into unreadable
// slivers. The full multiplicative product line below always lists every
// factor — the chart is the visual cue, the product line is the truth — so
// capping bars never hides an input.
const MAX_BARS = 12;

function inputLabel(input: InputUsed): string {
  return input.name ?? input.role_name ?? input.primitive_slug.replace(/-/g, " ");
}

function unitSuffix(unit: Unit | null | undefined): string {
  if (!unit) return "";
  if (unit.denominator) return `/${unit.denominator}`;
  if (unit.dimension && unit.dimension !== "currency") return unit.dimension;
  return "";
}

function truncate(s: string, max = 22): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

interface Datum {
  label: string;
  full: string;
  role: string;
  value: number;
  display: string;
}

export function CompositionChart({ scenario }: { scenario: Scenario }) {
  // Only inputs the evaluator actually sized can be drawn; never invent a value.
  const sized = scenario.inputs_used.filter(
    (i) => i.value != null && Number.isFinite(i.value) && (i.value ?? 0) > 0,
  );

  if (sized.length === 0) {
    return (
      <div className="text-[13px] text-[var(--fg-3)]">
        Inputs not enumerated for this scenario · the framework's primitive values aren't enriched
        yet.
      </div>
    );
  }

  const data: Datum[] = sized.map((input) => {
    const value = input.value ?? 0;
    const full = inputLabel(input);
    const suffix = unitSuffix(input.unit);
    return {
      label: truncate(full),
      full,
      role: input.role,
      value,
      display: `${formatCompact(value, input.unit)}${suffix ? ` ${suffix}` : ""}`,
    };
  });

  const shown = data.slice(0, MAX_BARS);
  const hiddenCount = data.length - shown.length;

  const config: ChartConfig = { value: { label: "Input" } };
  const height = Math.min(Math.max(shown.length * 44, 120), 420);

  // Honesty-fenced source footnote from the strongest-provenance sized input
  // (composite/modeled inputs carry no tier → null → no footnote rendered).
  const TIER_RANK: Record<string, number> = {
    regulator: 6,
    first_party: 5,
    aggregator: 4,
    analyst: 3,
    prediction_market: 2,
    community: 1,
  };
  const strongest = [...sized]
    .filter((i) => i.source_tier)
    .sort(
      (a, b) => (TIER_RANK[b.source_tier ?? ""] ?? 0) - (TIER_RANK[a.source_tier ?? ""] ?? 0),
    )[0];
  const source = sourceFootnote(strongest ?? null);

  return (
    <ChartFrame
      title="How this scenario composes"
      subtitle="Each bar is one input's own magnitude — the factors multiply, they don't sum"
      axisCaption="Input magnitude, log scale · labels carry the real value + unit"
      source={source}
    >
      <ChartContainer config={config} className="aspect-auto w-full" style={{ height }}>
        <BarChart accessibilityLayer data={shown} layout="vertical" margin={{ left: 8, right: 80 }}>
          <CartesianGrid horizontal={false} stroke="var(--border-1)" strokeDasharray="3 3" />
          {/* Log scale: inputs span orders of magnitude; labels carry the real value. */}
          <XAxis type="number" dataKey="value" scale="log" domain={["auto", "auto"]} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={150}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 13, fill: "var(--fg-2)" }}
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
                      <span className="text-[11px] text-[var(--fg-3)]">
                        {d.role.replace(/_/g, " ")}
                      </span>
                    </div>
                  );
                }}
              />
            }
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={36}>
            <LabelList
              dataKey="display"
              position="right"
              className="fill-[var(--fg-2)]"
              fontSize={13}
            />
          </Bar>
        </BarChart>
      </ChartContainer>
      {hiddenCount > 0 ? (
        <p className="mt-2 text-[12px] text-[var(--fg-3)]">
          Showing the first {MAX_BARS} of {data.length} inputs · all {data.length} factors are in
          the product line below.
        </p>
      ) : null}
      {/* The product line: makes the multiplicative (not additive) relationship explicit. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[12px] text-[var(--fg-3)]">
        <span className="font-medium text-[var(--fg-2)]">Multiplies to</span>
        {sized.map((input, i) => (
          <span key={input.primitive_slug} className="font-mono">
            {i > 0 && <span className="mx-0.5 text-[var(--fg-4)]">×</span>}
            {/* Each factor links to the source behind it (number-level provenance). */}
            <SourcedNumber input={input} />
          </span>
        ))}
        <span className="mx-0.5 text-[var(--fg-4)]">=</span>
        <span className="font-mono font-medium text-[var(--fg-1)]">
          {formatCompact(scenario.value, scenario.unit)}
        </span>
      </div>
    </ChartFrame>
  );
}
