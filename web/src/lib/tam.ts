// TAM-output helpers. A TAM is a scenario tree (never a scalar + error bar —
// Q1), so "the number" is really a low/mid/high band derived from the scenario
// set. These read-only helpers feed the artifact view, export, and the headline.
import { formatCompact, tierLabel } from "./format";
import type { Scenario, TAMOutput } from "./schemas";

// A TAM with a single scenario, or where every scenario shares one value, has no
// real spread — the UI should present it as a point estimate, not a range.
export function isDegenerate(tam: TAMOutput): boolean {
  if (tam.scenarios.length <= 1) return true;
  const values = tam.scenarios.map((s) => s.value);
  return Math.min(...values) === Math.max(...values);
}

// The middle scenario by value (median position). Used as the headline figure.
export function midScenario(tam: TAMOutput): Scenario {
  const sorted = [...tam.scenarios].sort((a, b) => a.value - b.value);
  const mid = Math.floor((sorted.length - 1) / 2);
  return sorted[mid];
}

export interface TamRange {
  low: number;
  high: number;
  mid: number;
}

// Low/high are the value extremes; mid is the median scenario's value.
export function tamRange(tam: TAMOutput): TamRange {
  const values = tam.scenarios.map((s) => s.value);
  return {
    low: Math.min(...values),
    high: Math.max(...values),
    mid: midScenario(tam).value,
  };
}

// Markdown export (U10). Banners become footnotes; scenario tree becomes a
// table. Mid headline first, then the full breakdown and the lineage summary.
export function tamToMarkdown(tam: TAMOutput): string {
  const range = tamRange(tam);
  const unit = midScenario(tam).unit;
  const lines: string[] = [];

  lines.push(`# TAM: ${tam.target.concept_name ?? tam.target.concept}`);
  lines.push("");
  lines.push(`**Mid estimate:** ${formatCompact(range.mid, unit)}`);
  if (!isDegenerate(tam)) {
    lines.push(`**Range:** ${formatCompact(range.low, unit)} – ${formatCompact(range.high, unit)}`);
  }
  lines.push("");

  const target = tam.target;
  lines.push("## Target");
  lines.push("");
  lines.push(`- Concept: \`${target.concept}\``);
  if (target.geo) lines.push(`- Geo: ${target.geo}`);
  if (target.time) lines.push(`- Time: ${target.time}`);
  lines.push(`- Expansion stage: ${target.expansion_stage}`);
  lines.push("");

  lines.push("## Scenarios");
  lines.push("");
  lines.push("| Scenario | Framework | Value |");
  lines.push("| --- | --- | --- |");
  for (const s of tam.scenarios) {
    const variant = s.framework_variant ? ` (${s.framework_variant})` : "";
    lines.push(
      `| ${s.definition} | ${s.framework}${variant} | ${formatCompact(s.value, s.unit)} |`,
    );
  }
  lines.push("");

  lines.push("## Method");
  lines.push("");
  lines.push(`- Method families: ${tam.method_families_used.map(tierLabel).join(", ")}`);
  lines.push(`- Independence score: ${tam.independence_score.toFixed(2)}`);
  lines.push("");

  // Collect every distinct banner across scenarios as footnotes.
  const banners = new Map<string, string>();
  for (const s of tam.scenarios) {
    for (const b of s.banners) {
      banners.set(`${b.kind}: ${b.message}`, b.kind);
    }
  }
  if (tam.uses_synthetic_primitives) {
    banners.set("synthetic: uses synthetic primitives", "synthetic");
  }
  if (tam.uses_modeled_composites) {
    banners.set("modeled: uses modeled composites", "modeled");
  }
  if (banners.size > 0) {
    lines.push("## Notes");
    lines.push("");
    for (const note of banners.keys()) {
      lines.push(`- ${note}`);
    }
    lines.push("");
  }

  lines.push(`*Generated from state \`${tam.state_hash}\` by ${tam.created_by}.*`);
  return lines.join("\n");
}
