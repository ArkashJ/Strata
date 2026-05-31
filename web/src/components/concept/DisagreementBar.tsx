/**
 * DisagreementView — the centerpiece of a concept page (docs/design
 * component-catalog "Disagreement view"). One competing measurement per row;
 * each bar is tinted by its source tier (the TierBadge palette) and scaled to
 * the max value in the set, so the eye reads disagreement as bar-length spread.
 * A STACKED · TABLE toggle swaps the bars for a SOURCE · TIER · VALUE · AS-OF
 * table; TIME SERIES is a placeholder (no historical series in the data layer
 * yet). Measurements arrive already-hydrated from the parent's useQueries so
 * this component stays presentational and testable.
 */

"use client";

import { useMemo, useState } from "react";

import { StaleChip } from "@/components/ui/StaleChip";
import { TierBadge } from "@/components/ui/TierBadge";
import { formatCompact } from "@/lib/format";
import type { AtomicPrimitive, PrimitiveDetail, SourceTier } from "@/lib/schemas";

type View = "stacked" | "table" | "timeseries";

// Only atomic primitives carry a comparable scalar value + source tier;
// composites are set-ops over other primitives and have no own measurement.
function isAtomic(p: PrimitiveDetail): p is AtomicPrimitive {
  return p.kind === "atomic_primitive";
}

export interface DisagreementRow {
  slug: string;
  name: string;
  value: number;
  tier: SourceTier;
  asOf: string;
  unit: AtomicPrimitive["unit"];
  // Wave 1 / AC1.7 — source freshness SLA (days), drives the stale chip.
  freshnessSlaDays?: number | null;
}

export function toRows(measurements: PrimitiveDetail[]): DisagreementRow[] {
  return measurements.filter(isAtomic).map((p) => ({
    slug: p.slug,
    name: p.name,
    value: p.value,
    tier: p.source.tier,
    asOf: p.as_of,
    unit: p.unit,
    freshnessSlaDays:
      (p.source as { freshness_sla_days?: number | null }).freshness_sla_days ?? null,
  }));
}

export function DisagreementView({ rows }: { rows: DisagreementRow[] }) {
  const [view, setView] = useState<View>("stacked");

  const { max, spread } = useMemo(() => {
    if (rows.length === 0) return { max: 0, spread: 0 };
    const vals = rows.map((r) => r.value);
    const hi = Math.max(...vals);
    const lo = Math.min(...vals);
    return { max: hi, spread: hi - lo };
  }, [rows]);

  return (
    <section className="canvas-card flex flex-col" style={{ borderRadius: "var(--r-4)" }}>
      <div className="flex items-center justify-between gap-4 px-6 pt-5 pb-3">
        <div className="flex flex-col gap-0.5">
          <h2 className="display text-[20px] text-[var(--fg-1)]">Disagreement view</h2>
          <p className="text-[12px] text-[var(--fg-3)] tabular-nums">
            {rows.length} measurement{rows.length === 1 ? "" : "s"}
            {rows.length > 1 ? ` · ${formatCompact(spread, rows[0]?.unit)} spread` : ""}
          </p>
        </div>
        <SegmentedToggle view={view} onChange={setView} />
      </div>

      <div className="px-6 pb-6">
        {view === "timeseries" ? (
          <div className="flex items-center justify-center px-6 py-12 text-center text-[13px] text-[var(--fg-3)]">
            Time-series view is not available yet — the data layer stores a single snapshot per
            measurement.
          </div>
        ) : view === "table" ? (
          <MeasurementTable rows={rows} />
        ) : (
          <BarRows rows={rows} max={max} />
        )}
      </div>
    </section>
  );
}

function SegmentedToggle({
  view,
  onChange,
}: {
  view: View;
  onChange: (v: View) => void;
}) {
  const options: { key: View; label: string }[] = [
    { key: "stacked", label: "STACKED" },
    { key: "table", label: "TABLE" },
    { key: "timeseries", label: "TIME SERIES" },
  ];
  return (
    <div
      role="tablist"
      aria-label="Disagreement view mode"
      className="flex gap-0.5 rounded-[var(--r-2)] bg-[var(--bg-2)] p-0.5"
    >
      {options.map((o) => {
        const active = view === o.key;
        return (
          <button
            key={o.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.key)}
            className={`rounded-[var(--r-1)] px-2.5 py-1 font-medium text-[10px] uppercase tracking-wide transition-colors ${
              active
                ? "bg-[var(--bg-1)] text-[var(--fg-1)] shadow-sm"
                : "text-[var(--fg-3)] hover:text-[var(--fg-2)]"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// Map a tier onto the same CSS-variable key TierBadge uses, so a bar and its
// badge always share a color. Mirrors TierBadge's TIER_KEY folding.
const TIER_KEY: Record<SourceTier, string> = {
  first_party: "first-party",
  regulator: "regulator",
  aggregator: "aggregator",
  analyst: "analyst",
  "analyst-paraphrase": "analyst",
  community: "community",
  onchain: "onchain",
  prediction_market: "prediction",
  "community-modeled": "community",
};

function BarRows({ rows, max }: { rows: DisagreementRow[]; max: number }) {
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((r) => {
        const pct = max > 0 ? Math.max(2, (r.value / max) * 100) : 2;
        const color = `var(--tier-${TIER_KEY[r.tier] ?? "community"})`;
        return (
          <li key={r.slug} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[13px] text-[var(--fg-1)] truncate">{r.name}</span>
              <span className="tam-num shrink-0 text-[13px] text-[var(--fg-1)] tabular-nums">
                {formatCompact(r.value, r.unit)}
              </span>
            </div>
            <div className="h-2.5 w-full rounded-[var(--r-round)] bg-[var(--bg-2)]">
              <div
                className="h-2.5 rounded-[var(--r-round)]"
                style={{ width: `${pct}%`, background: color }}
                title={`${r.tier} · ${r.value}`}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function MeasurementTable({ rows }: { rows: DisagreementRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
            <th className="pb-2 pr-4 font-medium">Source</th>
            <th className="pb-2 pr-4 font-medium">Tier</th>
            <th className="pb-2 pr-4 font-medium text-right">Value</th>
            <th className="pb-2 font-medium">As of</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.slug} className="border-t border-[var(--border-1)]">
              <td className="py-2.5 pr-4 text-[var(--fg-1)]">{r.name}</td>
              <td className="py-2.5 pr-4">
                <TierBadge tier={r.tier} />
              </td>
              <td className="py-2.5 pr-4 text-right font-mono tabular-nums text-[var(--fg-1)]">
                {formatCompact(r.value, r.unit)}
              </td>
              <td className="py-2.5 font-mono text-[var(--fg-3)]">
                <span className="inline-flex items-center gap-2">
                  {r.asOf}
                  <StaleChip asOf={r.asOf} freshnessSlaDays={r.freshnessSlaDays} />
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
