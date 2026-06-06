"use client";

// Forwardable question-driven market report (PR4). Clones the print-first
// letterhead, SectionTitle, canvas-card, KPI strip, ReportPrintStyles, and the
// SourcedNumber number-level-provenance pattern from tam/TamReport.tsx.
//
// Every displayed figure originates from a `provenance` row (a sourced registry
// primitive) or a `synthesis` (a TAM-field value the backend already proved
// reproducible). No number is authored here, and there are NO external/web
// citations — only the primitive's own cited source_url. Unsizable questions
// degrade to honest "No data in bank" gaps, never fabrications.

import Link from "next/link";

import { ReportCharts } from "@/components/questions/ReportCharts";
import { Button } from "@/components/ui/Button";
import { SourcedNumber } from "@/components/ui/SourcedNumber";
import { formatSnapshot, tierLabel } from "@/lib/format";
import type {
  AnswerProvenance,
  ConceptQuestionReport,
  QuestionCategory,
  ResolvedAnswer,
} from "@/lib/schemas";

// Spec order for the 10 analysis buckets — drives both grouping and section
// order. A category with no resolved answers is simply not rendered.
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

const CATEGORY_LABEL: Record<QuestionCategory, string> = {
  market_size: "Market size",
  growth_rate: "Growth rate",
  segmentation: "Segmentation",
  geography: "Geography",
  competition_share: "Competition & share",
  regulation: "Regulation",
  adoption: "Adoption",
  unit_economics: "Unit economics",
  risks: "Risks",
  methodology: "Methodology",
};

// Pull a /tam/<hash> permalink out of the backend's synthesis sentence so the
// reader can jump to the interactive, reproducible TAM. The hash is the only
// app-internal pointer we ever surface — never an external URL.
const TAM_HASH_RE = /\/tam\/([A-Za-z0-9]+)/;

export function QuestionReport({ report }: { report: ConceptQuestionReport }) {
  const concept = report.concept_name || report.concept_slug.replace(/-/g, " ");
  const answered = report.answers.filter((a) => a.status === "answered");
  const gaps = report.answers.filter((a) => a.status === "gap");
  const generated = new Date().toISOString().slice(0, 10);

  // Group answers by category, preserving the spec's bucket order.
  const groups = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    answers: report.answers.filter((a) => a.category === cat),
  })).filter((g) => g.answers.length > 0);

  return (
    <main className="tam-report mx-auto w-full max-w-[860px] px-8 py-10">
      <ReportPrintStyles />

      {/* Screen-only action bar (hidden in print). */}
      <div data-print-hide className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/c/${report.concept_slug}`}
          className="text-[13px] text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)]"
        >
          ← Back to concept
        </Link>
        <Button sm onClick={() => window.print()}>
          Print / Save as PDF
        </Button>
      </div>

      {/* Letterhead. */}
      <header className="border-b-2 border-[var(--fg-1)] pb-5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--fg-3)]">
            Strata · Analysis Report
          </span>
          <span className="font-mono text-[11px] text-[var(--fg-3)]">{generated}</span>
        </div>
        <h1 className="display mt-3 text-[34px] leading-[1.1] text-[var(--fg-1)]">{concept}</h1>
        <p className="mt-2 text-[13px] text-[var(--fg-3)]">
          The analyst questions, answered from the data bank ·{" "}
          <span className="font-mono text-[var(--fg-2)]">{report.concept_slug}</span>
        </p>
      </header>

      {/* Executive KPI strip — counts, not invented figures. */}
      <section className="report-block mt-7 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi label="Questions" value={String(report.answers.length)} emphasis />
        <Kpi label="Answered" value={String(answered.length)} />
        <Kpi label="Gaps" value={String(gaps.length)} />
        <Kpi
          label="Coverage"
          value={
            report.answers.length === 0
              ? "—"
              : `${Math.round((answered.length / report.answers.length) * 100)}%`
          }
        />
      </section>

      {/* Visual summary — derived from the answered/gap + provenance data. */}
      <ReportCharts report={report} />

      {report.answers.length === 0 ? (
        <p className="report-block mt-8 text-[13px] text-[var(--fg-3)]">
          No analysis questions apply to this concept yet.
        </p>
      ) : (
        groups.map((g) => (
          <section key={g.category} className="report-block mt-7">
            <SectionTitle>{CATEGORY_LABEL[g.category]}</SectionTitle>
            <div className="mt-3 flex flex-col gap-4">
              {g.answers.map((a) => (
                <AnswerCard key={a.question_id} answer={a} />
              ))}
            </div>
          </section>
        ))
      )}

      {/* Honesty footnotes — the modeled / honesty pattern from TamReport. */}
      <FootnotesBlock answers={report.answers} />

      <footer className="mt-10 border-t border-[var(--border-1)] pt-4 text-[11px] text-[var(--fg-3)]">
        Generated by Strata on {generated}. Every answered figure is snapshot-pinned to its cited
        source primitive, or reproducible at the linked /tam permalink. Gaps are stated honestly —
        no figure is authored or estimated. This is an analysis aid, not investment advice.
      </footer>
    </main>
  );
}

function Kpi({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className="canvas-card p-4">
      <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)]">{label}</div>
      <div
        className={`mt-1 tabular-nums text-[var(--fg-1)] ${
          emphasis ? "display text-[26px] leading-none" : "text-[18px] font-medium"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
      {children}
    </h2>
  );
}

// Build an InputUsed-shaped object from a provenance row so the existing
// SourcedNumber component links the figure to its source. The numeric value /
// pre-formatted display come off the ResolvedAnswer (already proven sourced).
function sourcedFromProvenance(answer: ResolvedAnswer, prov: AnswerProvenance) {
  return {
    role_name: prov.primitive_slug,
    role: "base_value" as const,
    primitive_slug: prov.primitive_slug,
    snapshot_sha256: prov.snapshot_sha256,
    value: answer.value ?? null,
    unit: null,
    source_tier: prov.source_tier ?? null,
    source_url: prov.source_url ?? null,
  };
}

function AnswerCard({ answer: a }: { answer: ResolvedAnswer }) {
  if (a.status === "gap") return <GapCard answer={a} />;

  const tamHash = a.synthesis?.match(TAM_HASH_RE)?.[1] ?? null;
  // The figure links to its source: a sourced provenance row when present,
  // otherwise the pre-formatted display (a synthesis number reproducible at the
  // linked TAM). Never an external citation.
  const sourcedRow = a.provenance.find((p) => p.source_url) ?? a.provenance[0] ?? null;

  return (
    <div className="canvas-card p-5">
      <div className="text-[14px] font-medium text-[var(--fg-1)]">{a.prompt}</div>

      <p className="mt-2 whitespace-pre-line text-[13px] leading-relaxed text-[var(--fg-2)]">
        {a.narrative}
      </p>

      {/* The headline figure, linked to its source primitive. */}
      {a.value != null ? (
        <div className="mt-3 flex items-baseline gap-2">
          {sourcedRow ? (
            <SourcedNumber
              input={sourcedFromProvenance(a, sourcedRow)}
              className="text-[16px] font-medium text-[var(--fg-1)]"
            />
          ) : (
            <span className="tabular-nums text-[16px] font-medium text-[var(--fg-1)]">
              {a.display ?? String(a.value)}
            </span>
          )}
          {a.display && sourcedRow ? (
            <span className="text-[12px] text-[var(--fg-3)]">({a.display})</span>
          ) : null}
        </div>
      ) : null}

      {/* tam_field synthesis: reproducible at the interactive TAM. */}
      {tamHash ? (
        <div className="mt-2 text-[11px] text-[var(--fg-3)]">
          Reproducible at{" "}
          <Link
            href={`/tam/${tamHash}`}
            className="font-mono underline decoration-dotted underline-offset-2 hover:text-[var(--accent)]"
          >
            /tam/{tamHash.slice(0, 12)}
          </Link>
        </div>
      ) : null}

      {/* Provenance snapshot tails — one row per sourced primitive behind it. */}
      {a.provenance.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1 border-t border-[var(--border-1)] pt-3 text-[11px] text-[var(--fg-3)]">
          {a.provenance.map((p) => (
            <li key={p.primitive_slug} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="text-[var(--fg-2)]">{p.primitive_slug}</span>
              {p.source_tier ? (
                <span className="font-mono uppercase tracking-wide">
                  {tierLabel(p.source_tier)}
                </span>
              ) : (
                <span className="font-mono uppercase tracking-wide">composite</span>
              )}
              <span className="font-mono">{formatSnapshot(p.snapshot_sha256)}</span>
              {p.as_of ? <span>as of {p.as_of}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function GapCard({ answer: a }: { answer: ResolvedAnswer }) {
  return (
    <div className="canvas-card border-dashed p-5">
      <div className="text-[14px] font-medium text-[var(--fg-2)]">{a.prompt}</div>
      <p className="mt-2 text-[13px] leading-relaxed text-[var(--fg-3)]">{a.narrative}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-[var(--fg-3)]">
        <span className="font-mono uppercase tracking-wide text-[var(--warning)]">
          No data in bank
        </span>
        {a.resource_target ? (
          <span>
            · would be sourced from{" "}
            <span className="font-mono text-[var(--fg-2)]">{a.resource_target}</span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

// Honesty footnotes — mirrors TamReport's FootnotesBlock. Surfaces the count of
// open gaps so a reader citing this report knows exactly what is unanswered.
function FootnotesBlock({ answers }: { answers: readonly ResolvedAnswer[] }) {
  const gaps = answers.filter((a) => a.status === "gap").length;
  if (gaps === 0) return null;
  return (
    <section className="report-block mt-7">
      <SectionTitle>Footnotes</SectionTitle>
      <ul className="mt-2 flex flex-col gap-1.5 text-[11px] text-[var(--fg-3)]">
        <li>
          <span className="font-mono uppercase text-[var(--warning)]">gap</span> — {gaps} question
          {gaps === 1 ? " has" : "s have"} no sourced figure in the data bank; shown honestly rather
          than estimated.
        </li>
      </ul>
    </section>
  );
}

// Print stylesheet, scoped to this report — identical contract to TamReport's:
// drop interactive chrome, tighten margins, keep blocks off page breaks.
function ReportPrintStyles() {
  return (
    <style>{`
      @media print {
        .tam-report [data-print-hide] { display: none !important; }
        .tam-report { max-width: none; padding: 0; }
        .tam-report .report-block { break-inside: avoid; page-break-inside: avoid; }
        .tam-report .canvas-card { box-shadow: none !important; border: 1px solid #ddd; }
      }
    `}</style>
  );
}
