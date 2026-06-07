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

import { ReportSummary } from "@/components/questions/ReportSummary";
import { Button } from "@/components/ui/Button";
import { SourcedNumber } from "@/components/ui/SourcedNumber";
import { tierColor } from "@/lib/chart-colors";
import { isPlaceholderSnapshot, tierLabel } from "@/lib/format";
// Single source of truth for bucket order + labels — shared with the summary
// charts so the per-section body and the visual band can't drift apart.
import { CATEGORY_LABEL, CATEGORY_ORDER } from "@/lib/report-metrics";
import type { AnswerProvenance, ConceptQuestionReport, ResolvedAnswer } from "@/lib/schemas";

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

      {/* Executive visual band — headline TAM, range, methodology, coverage,
          gaps, tier mix, and the source ledger — all derived from the payload. */}
      <ReportSummary report={report} />

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

      {/* Compact provenance — tier chips + an honest pin note. The full per-
          source detail (slug, snapshot, as-of) lives ONCE in the summary's
          source ledger, so cards no longer reprint the same five rows. */}
      {a.provenance.length > 0 ? <ProvenanceChips provenance={a.provenance} /> : null}
    </div>
  );
}

// Compact provenance for a single answer: one chip per distinct source tier
// (tier hue = the load-bearing colour contract) with a count, plus an honest
// "not pinned (demo)" note when any backing snapshot is a placeholder sentinel.
function ProvenanceChips({ provenance }: { provenance: readonly AnswerProvenance[] }) {
  const tierCounts = new Map<string, number>();
  for (const p of provenance) {
    const key = p.source_tier ?? "composite";
    tierCounts.set(key, (tierCounts.get(key) ?? 0) + 1);
  }
  const anyPlaceholder = provenance.some((p) => isPlaceholderSnapshot(p.snapshot_sha256));

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--border-1)] pt-3 text-[11px] text-[var(--fg-3)]">
      <span className="text-[var(--fg-3)]">
        {provenance.length} source{provenance.length === 1 ? "" : "s"}
      </span>
      {[...tierCounts.entries()].map(([tier, count]) => (
        <span
          key={tier}
          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
          style={
            tier === "composite"
              ? { color: "var(--fg-3)", backgroundColor: "var(--bg-2)" }
              : {
                  color: tierColor(tier),
                  backgroundColor: `color-mix(in srgb, ${tierColor(tier)} 14%, transparent)`,
                }
          }
        >
          {tier === "composite" ? "Composite" : tierLabel(tier)}
          {count > 1 ? <span className="opacity-70">{count}</span> : null}
        </span>
      ))}
      {anyPlaceholder ? (
        <span className="font-mono text-[10px] text-[var(--warning)]">not pinned (demo)</span>
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
