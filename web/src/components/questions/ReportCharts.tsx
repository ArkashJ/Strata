"use client";

// Charts for the analysis report. Every datum is DERIVED from the report payload
// (answered/gap counts per category, provenance source-tier mix) — nothing here
// is authored or estimated, matching the report's honesty contract. Reuses the
// agnostic recharts wrappers in components/charts.

import { DonutChart, type Slice } from "@/components/charts/DonutChart";
import { RadarChart } from "@/components/charts/RadarChart";
import { tierLabel } from "@/lib/format";
import type { ConceptQuestionReport, QuestionCategory } from "@/lib/schemas";

const CATEGORY_ORDER: readonly QuestionCategory[] = [
  "market_size",
  "growth_rate",
  "segmentation",
  "geography",
  "competition_share",
  "regulation",
  "adoption",
  "unit_economics",
  "risks",
  "methodology",
];

// Short axis labels so the radar stays legible.
const CATEGORY_SHORT: Record<QuestionCategory, string> = {
  market_size: "Size",
  growth_rate: "Growth",
  segmentation: "Segment",
  geography: "Geo",
  competition_share: "Share",
  regulation: "Reg",
  adoption: "Adopt",
  unit_economics: "Unit econ",
  risks: "Risks",
  methodology: "Method",
};

export function ReportCharts({ report }: { report: ConceptQuestionReport }) {
  const total = report.answers.length;
  if (total === 0) return null;

  const answered = report.answers.filter((a) => a.status === "answered").length;
  const gaps = total - answered;

  // Coverage radar: % of questions answered per category (only categories that
  // actually have questions for this concept).
  const radarData = CATEGORY_ORDER.map((cat) => {
    const inCat = report.answers.filter((a) => a.category === cat);
    if (inCat.length === 0) return null;
    const ans = inCat.filter((a) => a.status === "answered").length;
    return { axis: CATEGORY_SHORT[cat], coverage: Math.round((ans / inCat.length) * 100) };
  }).filter((d): d is { axis: string; coverage: number } => d !== null);

  // Source-tier mix: count every provenance row across answered questions.
  const tierCounts = new Map<string, number>();
  for (const a of report.answers) {
    for (const p of a.provenance) {
      const key = p.source_tier ? tierLabel(p.source_tier) : "Composite";
      tierCounts.set(key, (tierCounts.get(key) ?? 0) + 1);
    }
  }
  const tierSlices: Slice[] = [...tierCounts.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);

  const coveragePct = Math.round((answered / total) * 100);

  return (
    <section className="report-block mt-7">
      <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
        At a glance
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Answered vs gaps */}
        <ChartCard title="Answered vs gaps">
          <DonutChart
            data={[
              { label: "Answered", value: answered, fill: "#6366f1" },
              { label: "Gaps", value: gaps, fill: "#d4d4d8" },
            ]}
            centerValue={`${coveragePct}%`}
            centerLabel="coverage"
            height={200}
            animate={false}
          />
        </ChartCard>

        {/* Coverage by category */}
        <ChartCard title="Coverage by category">
          {radarData.length >= 3 ? (
            <RadarChart data={radarData} series={["coverage"]} height={200} animate={false} />
          ) : (
            <Empty />
          )}
        </ChartCard>

        {/* Source-tier mix of the sourced figures */}
        <ChartCard title="Source-tier mix">
          {tierSlices.length > 0 ? (
            <DonutChart
              data={tierSlices}
              centerValue={String([...tierCounts.values()].reduce((s, n) => s + n, 0))}
              centerLabel="sources"
              height={200}
              animate={false}
            />
          ) : (
            <Empty />
          )}
        </ChartCard>
      </div>
    </section>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="canvas-card p-4 text-[var(--fg-2)]">
      <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)]">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Empty() {
  return (
    <div className="grid h-[200px] place-items-center text-[12px] text-[var(--fg-3)]">
      Not enough data
    </div>
  );
}
