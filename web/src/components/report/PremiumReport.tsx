"use client";

// PremiumReport — the Coatue/Gartner-caliber composition of the report
// component system. It assembles the $1M-report skeleton from a TAMOutput:
//
//   headline → KPI strip → triangulation → method distribution → how-it-builds
//   (bridge) → sensitivity → competitive landscape → adoption → sources appendix
//
// Every section is honesty-fenced: a block renders only when its data exists on
// the TAM, otherwise it shows an explicit "no data yet" gap (Q20 — we never
// fabricate a CAGR, a competitor share, or an adoption curve). The optional
// `payload` carries data the core TAM API doesn't surface yet (penetration
// curve, competitive set); when absent those sections honestly say so.

import { TornadoChart } from "@/components/charts/TornadoChart";
import type { SensitivityResponse } from "@/components/charts/TornadoChart";
import { bridgeScenario, dedupeInputs, kpiFigures, methodEstimates } from "@/lib/premium-report";
import type { TAMOutput } from "@/lib/schemas";
import { midScenario } from "@/lib/tam";
import { type ComparisonRow, ComparisonTable, type InsightCard } from "./ComparisonTable";
import { KpiStrip } from "./KpiStrip";
import { type CurveSeries, PenetrationCurve, type PenetrationPoint } from "./PenetrationCurve";
import { RankedBarDistribution } from "./RankedBarDistribution";
import { ReportHeadline } from "./ReportHeadline";
import { SourceAppendixTable } from "./SourceAppendixTable";
import { StackedBridge } from "./StackedBridge";
import { TriangulationPanel } from "./TriangulationPanel";

// Optional extras the TAM API doesn't carry yet. All fields optional so the
// report renders against the bare TAM and degrades gracefully.
export interface PremiumReportPayload {
  sensitivity?: SensitivityResponse | null;
  // Adoption/penetration curve (Coatue S-curve). Sourced separately; absent →
  // the section states the gap honestly.
  penetration?: {
    data: PenetrationPoint[];
    series: CurveSeries[];
    todayX?: number | string;
    source?: string | null;
  } | null;
  // Competitive landscape (named players + shares). Absent → honest gap.
  competitive?: {
    rows: ComparisonRow[];
    insight?: InsightCard;
    valueLabel?: string;
    source?: string | null;
  } | null;
}

function SectionGap({ title, children }: { title: string; children: string }) {
  return (
    <section className="report-block rounded-[var(--r-3)] border border-dashed border-[var(--border-2)] p-5">
      <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-3)]">
        {title}
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-[var(--fg-3)]">{children}</p>
    </section>
  );
}

export function PremiumReport({
  tam,
  payload,
}: {
  tam: TAMOutput;
  payload?: PremiumReportPayload;
}) {
  const concept = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
  const kpi = kpiFigures(tam);
  const estimates = methodEstimates(tam);
  const bridge = bridgeScenario(tam);
  const inputs = dedupeInputs(tam);
  const mid = midScenario(tam);

  return (
    <div className="flex flex-col gap-9">
      {/* Executive summary — editorial headline stating the takeaway. */}
      <ReportHeadline
        eyebrow="Executive summary"
        headline={`${concept} is a ${kpi.headline} market`}
        subtitle={`Total addressable market · USD nominal · ${tam.method_families_used.length} independent method${
          tam.method_families_used.length === 1 ? "" : "s"
        }`}
        source={`permalink /tam/${tam.state_hash.slice(0, 12)} · generated ${tam.created_at.slice(0, 10)}`}
      >
        <KpiStrip
          items={[
            {
              label: "Triangulated TAM",
              value: kpi.headline,
              emphasis: true,
              note: kpi.modeled ? "leans modeled" : undefined,
            },
            { label: "Range", value: kpi.range },
            { label: "Methods", value: kpi.methods },
            { label: "Independence", value: kpi.independence },
          ]}
        />
      </ReportHeadline>

      {/* Triangulation — the #1 credibility marker. */}
      <TriangulationPanel
        convergence={tam.convergence}
        singleMethod={
          tam.convergence
            ? null
            : {
                family: tam.method_families_used[0] ?? mid.framework,
                value: mid.value,
                unit: mid.unit,
              }
        }
        className="report-block"
      />

      {/* Method distribution — how each method sized the market. */}
      {estimates.length > 1 ? (
        <RankedBarDistribution
          className="report-block"
          headline="How the methods compare"
          subtitle="Each independent method's estimate, ranked"
          rows={estimates.map((e) => ({ label: e.label, value: e.value, display: e.display }))}
          source={`source: ${tam.method_families_used.length} method famil${
            tam.method_families_used.length === 1 ? "y" : "ies"
          } · /tam/${tam.state_hash.slice(0, 12)}`}
        />
      ) : null}

      {/* How it builds — the multiplicative bridge to the TAM. */}
      {bridge ? (
        <StackedBridge
          className="report-block"
          headline="How the number builds"
          subtitle={`${bridge.scenario.framework.replace(/-/g, " ")} · each factor sourced or modeled`}
          steps={bridge.chain.steps}
          total={bridge.chain.total}
          totalDisplay={bridge.chain.totalDisplay}
        />
      ) : null}

      {/* Sensitivity — which assumption to defend first. */}
      {payload?.sensitivity && payload.sensitivity.inputs.length > 0 ? (
        <section className="report-block">
          <TornadoChart data={payload.sensitivity} />
        </section>
      ) : (
        <SectionGap title="Sensitivity">
          Sensitivity analysis loads on the interactive TAM. No perturbable inputs were supplied to
          this rendering.
        </SectionGap>
      )}

      {/* Competitive landscape — named players + shares (honest gap when absent). */}
      {payload?.competitive && payload.competitive.rows.length > 0 ? (
        <ComparisonTable
          className="report-block"
          headline="Competitive landscape"
          subtitle={payload.competitive.valueLabel ?? "Named players, by share"}
          rows={payload.competitive.rows}
          insight={payload.competitive.insight}
          source={payload.competitive.source ?? null}
        />
      ) : (
        <SectionGap title="Competitive landscape">
          No competitive set is sourced for this market yet. Named-player shares would be added as
          sourced primitives — not estimated here.
        </SectionGap>
      )}

      {/* Adoption / penetration curve (honest gap when absent). */}
      {payload?.penetration && payload.penetration.data.length > 0 ? (
        <PenetrationCurve
          className="report-block"
          headline="Adoption is still early"
          subtitle="Penetration over time vs analog technologies"
          data={payload.penetration.data}
          series={payload.penetration.series}
          todayX={payload.penetration.todayX}
          source={payload.penetration.source ?? null}
        />
      ) : (
        <SectionGap title="Adoption curve">
          No sourced adoption/penetration series for this market yet. Analog-technology curves would
          be sourced primitives, not projected here.
        </SectionGap>
      )}

      {/* Sources appendix — every figure named + dated + tiered + pinned. */}
      <SourceAppendixTable className="report-block" rows={inputs} />
    </div>
  );
}
