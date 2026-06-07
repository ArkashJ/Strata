// Pure derivation layer for the analysis report's VISUAL summary.
//
// The report payload (ConceptQuestionReport) already proved every number
// sourced or TAM-field-derived. This module reads those resolved answers and
// shapes them for the charts — it AUTHORS NOTHING. A metric is only present
// when the backing question resolved; an unanswered metric is `null` and the
// chart omits it (the report's honesty contract, applied to the visual layer).
//
// The headline $ figures come from the curated TAM-field questions, whose
// question_ids are stable across concepts (the question bank is global). We key
// off those ids rather than parsing prose, and fall back to null when absent.

import type { ConceptQuestionReport, QuestionCategory, ResolvedAnswer } from "@/lib/schemas";

// A disagreement / convergence multiple, e.g. "72.7×". One decimal under 100×
// keeps it precise without drifting far from the report's canonical "72.69×";
// whole numbers above that (the spread is already the headline, not a tick).
export function formatRatio(ratio: number): string {
  return `${ratio >= 100 ? Math.round(ratio) : ratio.toFixed(1)}×`;
}

// Canonical TAM-field question ids → the metric each resolves. Stable curated
// ids from data/questions; absence just means that metric isn't rendered.
//
// CONTRACT (keep in sync with data/questions if an id is renamed): a rename
// silently nulls the metric here, which degrades the range chart to the honest
// "single-method" line — looking like the concept genuinely has one method when
// really the id just wasn't found. If you rename one of these, update it here.
// Expected scales: rangeLow = USD; spreadRatio/convergenceRatio = dimensionless
// multiples (high÷low, family agreement); independence = 0..1; the rest = counts.
const METRIC_QUESTION = {
  headlineTam: "Q-MS-008", // triangulated midpoint, the headline $ figure
  rangeLow: "Q-MS-007", // range floor (lowest method family)
  spreadRatio: "Q-MS-001", // high ÷ low, the disagreement multiple
  convergenceRatio: "Q-METH-004", // how tightly independent families converge
  methodFamilies: "Q-METH-002", // count of independent method families
  independence: "Q-METH-001", // 0..1 — less shared input = higher
  scenarios: "Q-METH-006", // breadth of the scenario tree
} as const;

export interface RangeMetrics {
  low: number;
  high: number;
  mid: number | null;
  spreadRatio: number | null; // high ÷ low
}

export interface MethodMetrics {
  families: number | null;
  independence: number | null; // 0..1
  convergenceRatio: number | null;
  scenarios: number | null;
}

export interface CategoryCoverage {
  category: QuestionCategory;
  answered: number;
  total: number;
}

export interface TierSlice {
  tier: string; // raw tier key ("regulator", "analyst-paraphrase", …)
  count: number;
}

// One distinct sourced primitive that backs at least one answer — the
// "competing measurements" ledger, deduped across the whole report so the same
// five sources aren't reprinted on every card.
export interface LedgerRow {
  primitive_slug: string;
  source_tier: string | null;
  source_url: string | null;
  snapshot_sha256: string;
  as_of: string | null;
  usedBy: number; // how many answers cite it — a crude salience signal
}

export interface ReportMetrics {
  headlineTam: number | null;
  headlineDisplay: string | null;
  range: RangeMetrics | null;
  method: MethodMetrics;
  coverage: CategoryCoverage[]; // only categories with questions, spec order
  answered: number;
  gaps: number;
  total: number;
  coveragePct: number;
  tierMix: TierSlice[]; // descending by count
  ledger: LedgerRow[]; // descending by usedBy
  gapTargets: { category: QuestionCategory; prompt: string; resourceTarget: string | null }[];
}

export const CATEGORY_ORDER: readonly QuestionCategory[] = [
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

export const CATEGORY_LABEL: Record<QuestionCategory, string> = {
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

export const CATEGORY_SHORT: Record<QuestionCategory, string> = {
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

function answerById(answers: readonly ResolvedAnswer[], id: string): ResolvedAnswer | null {
  return answers.find((a) => a.question_id === id && a.status === "answered") ?? null;
}

// A metric value is trustworthy only if the answer carries provenance OR a
// reproducible synthesis — the same fence the backend enforces. We re-check it
// here so a future schema slip can't leak a bare number into a chart.
function metricValue(a: ResolvedAnswer | null): number | null {
  if (!a || a.value == null) return null;
  const backed = a.provenance.length > 0 || Boolean(a.synthesis);
  return backed ? a.value : null;
}

export function deriveReportMetrics(report: ConceptQuestionReport): ReportMetrics {
  const answers = report.answers;
  const total = answers.length;
  const answered = answers.filter((a) => a.status === "answered").length;
  const gaps = total - answered;

  const headlineAnswer = answerById(answers, METRIC_QUESTION.headlineTam);
  const headlineTam = metricValue(headlineAnswer);

  const low = metricValue(answerById(answers, METRIC_QUESTION.rangeLow));
  const spreadRatio = metricValue(answerById(answers, METRIC_QUESTION.spreadRatio));
  // High is not its own question — it's the floor times the disagreement
  // multiple (high ÷ low = spread). Only compose it when both are real.
  const high = low != null && spreadRatio != null ? low * spreadRatio : null;
  // Guard the log axis: a floor of 0 / negative (z.number() doesn't constrain
  // sign) would make log10 yield -Infinity/NaN and break the range chart. Only
  // a strictly-positive band is plottable; otherwise degrade to no range.
  const range: RangeMetrics | null =
    low != null && low > 0 && high != null && high > 0
      ? { low, high, mid: headlineTam != null && headlineTam > 0 ? headlineTam : null, spreadRatio }
      : null;

  const method: MethodMetrics = {
    families: metricValue(answerById(answers, METRIC_QUESTION.methodFamilies)),
    independence: metricValue(answerById(answers, METRIC_QUESTION.independence)),
    convergenceRatio: metricValue(answerById(answers, METRIC_QUESTION.convergenceRatio)),
    scenarios: metricValue(answerById(answers, METRIC_QUESTION.scenarios)),
  };

  const coverage: CategoryCoverage[] = CATEGORY_ORDER.map((category) => {
    const inCat = answers.filter((a) => a.category === category);
    return {
      category,
      answered: inCat.filter((a) => a.status === "answered").length,
      total: inCat.length,
    };
  }).filter((c) => c.total > 0);

  // Source-tier mix — one count per provenance row across every answer.
  const tierCounts = new Map<string, number>();
  for (const a of answers) {
    for (const p of a.provenance) {
      const key = p.source_tier ?? "composite";
      tierCounts.set(key, (tierCounts.get(key) ?? 0) + 1);
    }
  }
  const tierMix: TierSlice[] = [...tierCounts.entries()]
    .map(([tier, count]) => ({ tier, count }))
    .sort((a, b) => b.count - a.count);

  // Deduped competing-source ledger, keyed by primitive slug.
  const ledgerMap = new Map<string, LedgerRow>();
  for (const a of answers) {
    for (const p of a.provenance) {
      const existing = ledgerMap.get(p.primitive_slug);
      if (existing) {
        existing.usedBy += 1;
      } else {
        ledgerMap.set(p.primitive_slug, {
          primitive_slug: p.primitive_slug,
          source_tier: p.source_tier ?? null,
          source_url: p.source_url ?? null,
          snapshot_sha256: p.snapshot_sha256,
          as_of: p.as_of ?? null,
          usedBy: 1,
        });
      }
    }
  }
  const ledger = [...ledgerMap.values()].sort((a, b) => b.usedBy - a.usedBy);

  // Gap targets — what the bank would need next, deduped by resource target.
  const gapTargets = answers
    .filter((a) => a.status === "gap")
    .map((a) => ({
      category: a.category,
      prompt: a.prompt,
      resourceTarget: a.resource_target ?? null,
    }));

  return {
    headlineTam,
    headlineDisplay: headlineAnswer?.display ?? null,
    range,
    method,
    coverage,
    answered,
    gaps,
    total,
    coveragePct: total === 0 ? 0 : Math.round((answered / total) * 100),
    tierMix,
    ledger,
    gapTargets,
  };
}
