"use client";

// The report's executive band — the page-one surface a VC actually reads first.
// Replaces the three disconnected donuts (+ a screen of whitespace) with one
// cohesive dashboard, in the Sourced-Ledger register: a dominant headline TAM
// in Instrument Serif, the football-field range that frames it, the methodology
// trust signals, coverage vs gaps, and the source ledger underneath. Every datum
// is derived from the report payload — nothing authored.
//
// App-specific by design: depends on the app design tokens + tabular Geist Mono.

import { CoverageBars } from "@/components/questions/CoverageBars";
import { GapMap } from "@/components/questions/GapMap";
import { MethodologyStrip } from "@/components/questions/MethodologyStrip";
import { SourceLedger } from "@/components/questions/SourceLedger";
import { TamRangeField } from "@/components/questions/TamRangeField";
import { tierColor } from "@/lib/chart-colors";
import { tierLabel } from "@/lib/format";
import {
  type ReportMetrics,
  type TierSlice,
  deriveReportMetrics,
  formatRatio,
} from "@/lib/report-metrics";
import type { ConceptQuestionReport } from "@/lib/schemas";

export function ReportSummary({ report }: { report: ConceptQuestionReport }) {
  const m = deriveReportMetrics(report);
  if (m.total === 0) return null;

  return (
    // NOT one break-inside-avoid block: the whole band is taller than a page, so
    // marking it un-splittable would bump it past the KPI strip and leave page 1
    // empty. It flows from page 1; each inner panel guards its own break.
    <section className="mt-8 flex flex-col gap-8">
      {/* Headline + range — the lead. */}
      <div className="report-block grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,260px)_1fr] lg:items-center">
        <Headline metrics={m} />
        {m.range ? (
          <TamRangeField range={m.range} headlineDisplay={m.headlineDisplay} />
        ) : (
          <div className="text-[13px] text-[var(--fg-3)]">
            This concept resolves to a single method — no cross-method range to plot.
          </div>
        )}
      </div>

      {/* Methodology trust signals. */}
      <MethodologyStrip method={m.method} className="report-block" />

      {/* Coverage vs gaps, side by side. */}
      <div className="grid grid-cols-1 gap-7 md:grid-cols-2">
        <Panel
          title="Coverage by category"
          hint={`${m.answered} of ${m.total} answered · ${m.coveragePct}%`}
        >
          <CoverageBars coverage={m.coverage} className="mt-3" />
        </Panel>
        <Panel title="Where the bank is thin" hint={`${m.gaps} open gaps`}>
          <GapMap coverage={m.coverage} gapTargets={m.gapTargets} className="mt-3" />
        </Panel>
      </div>

      {/* Source-tier mix as a compact stacked bar. */}
      {m.tierMix.length > 0 ? (
        <Panel
          title="Source-tier mix"
          hint={`${m.tierMix.reduce((s, t) => s + t.count, 0)} citations`}
        >
          <TierMixBar mix={m.tierMix} className="mt-3" />
        </Panel>
      ) : null}

      {/* The full provenance ledger. */}
      {m.ledger.length > 0 ? (
        <Panel title="Sources behind the answered figures" hint={`${m.ledger.length} distinct`}>
          <SourceLedger rows={m.ledger} className="mt-3" />
        </Panel>
      ) : null}
    </section>
  );
}

function Headline({ metrics: m }: { metrics: ReportMetrics }) {
  const families = m.method.families;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]">
        Triangulated headline TAM
      </div>
      <div className="display mt-1 text-[52px] leading-[0.95] tabular-nums text-[var(--fg-1)]">
        {m.headlineDisplay ?? "—"}
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-[var(--fg-3)]">
        {families != null && families >= 2
          ? `Midpoint of ${families} independent method families.`
          : "Single-method estimate — read as a point, not a corroborated range."}
        {m.range?.spreadRatio != null
          ? ` Methods disagree ${formatRatio(m.range.spreadRatio)}.`
          : ""}
      </p>
    </div>
  );
}

function Panel({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="report-block">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
          {title}
        </h3>
        {hint ? (
          <span className="font-mono text-[10px] tabular-nums text-[var(--fg-3)]">{hint}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function TierMixBar({ mix, className }: { mix: readonly TierSlice[]; className?: string }) {
  const total = mix.reduce((s, t) => s + t.count, 0);
  if (total === 0) return null;
  return (
    <div className={className}>
      <div className="flex h-3 overflow-hidden rounded-full">
        {mix.map((t) => (
          <div
            key={t.tier}
            style={{
              width: `${(t.count / total) * 100}%`,
              backgroundColor: t.tier === "composite" ? "var(--fg-4)" : tierColor(t.tier),
            }}
            title={`${t.tier}: ${t.count}`}
          />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
        {mix.map((t) => (
          <span
            key={t.tier}
            className="inline-flex items-center gap-1.5 text-[11px] text-[var(--fg-3)]"
          >
            <span
              className="h-2.5 w-2.5 rounded-[2px]"
              style={{
                backgroundColor: t.tier === "composite" ? "var(--fg-4)" : tierColor(t.tier),
              }}
            />
            {t.tier === "composite" ? "Composite" : tierLabel(t.tier)}
            <span className="font-mono tabular-nums text-[var(--fg-4)]">{t.count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
