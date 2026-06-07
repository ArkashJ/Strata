// Pure derivation layer that shapes a TAMOutput into the props the premium
// report components consume. It AUTHORS NOTHING — every figure here comes from
// the TAM's own scenarios/inputs/convergence. A section's data is `null`/empty
// when the TAM doesn't carry it, and the composer renders an honest gap rather
// than fabricating (Q20). Kept framework-agnostic and dependency-light so it is
// unit-testable without rendering.

import { formatCompact } from "./format";
import type { InputUsed, Scenario, TAMOutput, Unit } from "./schemas";
import { isDegenerate, midScenario, tamRange } from "./tam";

const MULTIPLICATIVE_LENSES = new Set([
  "cost_efficiency",
  "revenue_generation",
  "latent_demand",
  "platform_throughput",
  "productivity_uplift",
]);

// One de-duped row per sourced input across all scenarios (first occurrence
// wins), the basis of the sources appendix and the bridge.
export function dedupeInputs(tam: TAMOutput): InputUsed[] {
  const seen = new Map<string, InputUsed>();
  for (const s of tam.scenarios) {
    for (const iu of s.inputs_used) {
      if (!seen.has(iu.primitive_slug)) seen.set(iu.primitive_slug, iu);
    }
  }
  return [...seen.values()];
}

// Ranked comparison of the method estimates (one bar per scenario) — the
// "how the methods compare" distribution. Sorted desc by the caller's chart.
export interface MethodEstimate {
  key: string;
  label: string;
  value: number;
  display: string;
}

export function methodEstimates(tam: TAMOutput): MethodEstimate[] {
  return tam.scenarios.map((s, i) => ({
    key: `${s.framework}-${s.framework_variant ?? ""}-${i}`,
    label: s.framework.replace(/-/g, " "),
    value: s.value,
    display: formatCompact(s.value, s.unit),
  }));
}

// The multiplicative factor chain for a single method, for the StackedBridge.
// Returns null when the scenario isn't a clean product of >1 sourced factors —
// the bridge then doesn't render (we never invent a chain).
export interface FactorChain {
  steps: { label: string; factor: number; display: string; tier?: string | null }[];
  total: number;
  totalDisplay: string;
  unit: Unit;
}

export function factorChain(scenario: Scenario): FactorChain | null {
  if (!MULTIPLICATIVE_LENSES.has(scenario.lens)) return null;
  const usable = scenario.inputs_used.filter((iu) => iu.value != null);
  if (usable.length < 2) return null;
  return {
    steps: usable.map((iu) => ({
      label: iu.name ?? iu.role_name,
      factor: iu.value as number,
      display: formatCompact(iu.value as number, iu.unit ?? null),
      tier: iu.source_tier ?? null,
    })),
    total: scenario.value,
    totalDisplay: formatCompact(scenario.value, scenario.unit),
    unit: scenario.unit,
  };
}

// Pick the most informative scenario for the bridge: the multiplicative method
// with the most sourced factors. Null when no scenario qualifies.
export function bridgeScenario(tam: TAMOutput): { scenario: Scenario; chain: FactorChain } | null {
  let best: { scenario: Scenario; chain: FactorChain } | null = null;
  for (const s of tam.scenarios) {
    const chain = factorChain(s);
    if (chain && (!best || chain.steps.length > best.chain.steps.length)) {
      best = { scenario: s, chain };
    }
  }
  return best;
}

// The executive KPI figures, pre-formatted. `modeled` marks the headline when
// the TAM leans on a modeled/synthetic input so the strip reads honestly.
export interface KpiFigures {
  headline: string;
  range: string;
  methods: string;
  independence: string;
  modeled: boolean;
}

export function kpiFigures(tam: TAMOutput): KpiFigures {
  const range = tamRange(tam);
  const unit = midScenario(tam).unit;
  return {
    headline: formatCompact(range.mid, unit),
    range: isDegenerate(tam)
      ? "single point"
      : `${formatCompact(range.low, unit)} – ${formatCompact(range.high, unit)}`,
    methods: String(tam.method_families_used.length),
    independence: tam.independence_score.toFixed(2),
    modeled: tam.uses_synthetic_primitives || tam.uses_modeled_composites,
  };
}
