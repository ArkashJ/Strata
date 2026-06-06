// Build Studio reveal sequencing (PURE — no React, no DOM).
//
// deriveBuildSteps walks a finished TAMOutput the way ScenarioGraph.buildGraph
// lays it out (apex target → framework nodes → base_value role leaves) and emits
// an ordered list of reveal steps. The Build Studio plays these back one at a
// time ("watch it build") and the StudioStepRail lists them as a running ledger.
//
// Why this lives apart from the view (docs/architecture/DIAGRAMS flow 31): the
// staged reveal and the finished TAM are the SAME artifact at cursor=0 vs
// cursor=last. The cursor is ephemeral UI; the steered tree round-trips through
// BuildState (?s=) + /build/<hash>, so this function must be deterministic and
// depend only on its inputs — never on wall-clock, randomness, or module state.
//
// Governance: numbers are formatted by the caller via format.ts (tabular mono);
// the tier dot color comes from the tier ramp (provenance), never the lens cool
// family. This module only carries the raw fields each node needs.

import { lensLabel } from "./format";
import type { AnalysisLens, InputUsed, Scenario, TAMOutput } from "./schemas";
import type { BuildState } from "./state-hash";

// The fixed multiplicative order a framework's inputs read in (base_value first),
// so a role leaf reveals left-to-right the way the equation is written.
const ROLE_ORDER: Record<string, number> = {
  base_value: 0,
  growth_index: 1,
  regime_modifier: 2,
  conditional_adjustment: 3,
};

export type BuildStepKind = "apex" | "framework" | "role";

// One reveal step. Steps are DERIVED, never persisted.
export interface BuildStep {
  // Stable id, matching ScenarioGraph node ids so a graph can slice its node /
  // edge arrays by the set of revealed ids. apex="target", framework=`f-<slug>`,
  // role=`p-f-<slug>-<primitive_slug>`.
  id: string;
  kind: BuildStepKind;
  // Human label for the rail + the aria-live headline.
  label: string;
  // The partial market size up to and including this node. For an apex step it is
  // the mean of the lens's scenario values (the headline). For a framework step
  // it is that framework's own scenario value (the method's standalone number).
  // For a role leaf it is the running partial product of its framework's
  // base_value inputs up to and including this leaf — what the count-up speaks.
  runningValue: number;
  // The framework this step belongs to (null on the apex). Lets the graph + rail
  // group leaves under their method.
  frameworkSlug: string | null;
  // Number-level provenance, carried straight from InputUsed (role steps only).
  // source_url is null for composites (no single source) and for non-role steps.
  // A null url with a present step means MODELED / composite — the caller renders
  // the honest MODELED label instead of a link.
  sourceUrl: string | null;
  // Raw source tier string (e.g. "regulator") → tier-ramp dot color downstream.
  tier: string | null;
  // The raw snapshot sha (role steps); the caller runs formatSnapshot() so the
  // demo sentinel reads "not pinned (demo)" rather than a fake green check.
  snapshot: string | null;
  // The bound primitive's value + unit, for the rail's per-row figure (role only).
  value: number | null;
  unit: Scenario["unit"] | null;
}

// Mean of an array (used for the apex headline). Empty → 0 (caller guards lens).
function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

// The base_value inputs of a scenario, in equation reading order.
function orderedRoleInputs(scenario: Scenario): InputUsed[] {
  return [...scenario.inputs_used]
    .filter((i) => i.role === "base_value")
    .sort((a, b) => (ROLE_ORDER[a.role] ?? 99) - (ROLE_ORDER[b.role] ?? 99));
}

// The running partial PRODUCT of a framework's base_value inputs up to (and
// including) index `upTo`. Inputs with a null value (composite / pre-enrichment)
// do not break the chain — they pass through as a factor of 1 so the running
// number stays honest rather than collapsing to 0.
function partialProduct(inputs: InputUsed[], upTo: number): number {
  let product = 1;
  let seen = false;
  for (let i = 0; i <= upTo; i++) {
    const v = inputs[i]?.value;
    if (typeof v === "number" && Number.isFinite(v)) {
      product *= v;
      seen = true;
    }
  }
  // No numeric factor seen yet → 0, so the headline doesn't claim a phantom $1.
  return seen ? product : 0;
}

// The scenarios for a single lens, ordered most-divergent-LAST: a method whose
// value sits furthest from the lens midpoint reveals at the end (drama without
// theater — the spread is the story, not a flourish).
function lensScenarios(tam: TAMOutput, lens: AnalysisLens): Scenario[] {
  const inLens = tam.scenarios.filter((s) => s.lens === lens);
  const mid = mean(inLens.map((s) => s.value));
  return [...inLens].sort((a, b) => Math.abs(a.value - mid) - Math.abs(b.value - mid));
}

// deriveBuildSteps — the reveal script for one lens of a finished TAM.
//
// state is accepted for signature symmetry with the view (and future scope-aware
// labelling); the ordering is fully determined by `tam` + `lens`, so the output
// is deterministic and reproduces from a round-tripped BuildState.
export function deriveBuildSteps(
  tam: TAMOutput,
  lens: AnalysisLens,
  _state: BuildState,
): BuildStep[] {
  const scenarios = lensScenarios(tam, lens);
  if (scenarios.length === 0) return [];

  const apexValue = mean(scenarios.map((s) => s.value));
  const steps: BuildStep[] = [
    {
      id: "target",
      kind: "apex",
      label: tam.target.concept_name ?? tam.target.concept.replace(/-/g, " "),
      runningValue: apexValue,
      frameworkSlug: null,
      sourceUrl: null,
      tier: null,
      snapshot: null,
      value: null,
      unit: scenarios[0]?.unit ?? null,
    },
  ];

  for (const scenario of scenarios) {
    const fId = `f-${scenario.framework}`;
    steps.push({
      id: fId,
      kind: "framework",
      label: lensLabel(scenario.lens),
      runningValue: scenario.value,
      frameworkSlug: scenario.framework,
      sourceUrl: null,
      tier: null,
      snapshot: null,
      value: scenario.value,
      unit: scenario.unit,
    });

    const inputs = orderedRoleInputs(scenario);
    inputs.forEach((input, idx) => {
      steps.push({
        id: `p-${fId}-${input.primitive_slug}`,
        kind: "role",
        label: input.name ?? input.role_name ?? input.role.replace(/_/g, " "),
        runningValue: partialProduct(inputs, idx),
        frameworkSlug: scenario.framework,
        sourceUrl: input.source_url ?? null,
        tier: input.source_tier ?? null,
        snapshot: input.snapshot_sha256 ?? null,
        value: input.value ?? null,
        unit: input.unit ?? null,
      });
    });
  }

  return steps;
}

// Resume-at-edit: the cursor index of the first step bound to a given primitive
// slug (the role leaf the user just steered). Returns the step count (reveal-all)
// when the slug is absent, so a steer never rewinds the reveal before its edit.
export function stepIndexForRole(steps: BuildStep[], primitiveSlug: string): number {
  const idx = steps.findIndex((s) => s.kind === "role" && s.id.endsWith(`-${primitiveSlug}`));
  return idx === -1 ? steps.length : idx;
}
