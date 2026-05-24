/**
 * Mock API layer — shapes mirror the planned FastAPI responses (backend task #17).
 *
 * When the real backend lands, swap each function body for a `fetch()` call against
 * /c/{slug}, /p/{slug}, /f/{slug}, /build/{hash} — the response types stay identical.
 */

export type SourceTier =
  | "first_party"
  | "regulator"
  | "aggregator"
  | "analyst"
  | "community"
  | "onchain"
  | "prediction_market"
  | "community_modeled";

export type MethodFamily =
  | "top_down_spend"
  | "bottoms_up_seats"
  | "comparable_revenue"
  | "analog_penetration"
  | "value_chain";

export interface PrimitiveRef {
  slug: string;
  name: string;
  value: number;
  unit_label: string;
  as_of: string;
  source: { slug: string; tier: SourceTier; url: string };
}

export interface ScenarioInput {
  role: "base_value" | "growth_index" | "regime_modifier" | "conditional_adjustment";
  primitive_slug: string;
  primitive_name: string;
  value: number;
  unit_label: string;
}

export interface Scenario {
  definition: string;
  value: number;
  unit_label: string;
  framework_slug: string;
  framework_name: string;
  method_family: MethodFamily;
  inputs_used: ScenarioInput[];
}

export interface BuildResponse {
  hash: string;
  target: {
    concept_slug: string;
    concept_name: string;
    geo: string;
    time: string;
  };
  scenarios: Scenario[];
  triangulated_range: { low: number; high: number };
  independence_score: number;
  method_families_used: MethodFamily[];
  uses_synthetic_primitives: boolean;
  uses_modeled_composites: boolean;
}

export interface Interpretation {
  label: string;
  narrow_or_broad: "narrow" | "broad" | "default";
  concept_slug: string;
  constraints: {
    qualitative: string;
    quantitative: string;
    industry: string;
    geo: string;
  };
  preview_range: { low: number; high: number };
}

const PC_DOC_GEN_BUILD: BuildResponse = {
  hash: "3f7a9c8e0000000000000000000000000000000000000000000000000000face",
  target: {
    concept_slug: "pc-doc-gen-tam-us",
    concept_name: "Document automation for P&C insurance carriers, US",
    geo: "US",
    time: "2026-05-21",
  },
  scenarios: [
    {
      definition: "Bottoms-up by carrier seat",
      value: 47_000_000,
      unit_label: "$/yr",
      framework_slug: "bottoms-up-by-carrier-seat",
      framework_name: "Bottoms-up by carrier seat",
      method_family: "bottoms_up_seats",
      inputs_used: [
        {
          role: "base_value",
          primitive_slug: "n-pc-carriers-us",
          primitive_name: "# of P&C carriers, US",
          value: 2_800,
          unit_label: "carriers",
        },
        {
          role: "base_value",
          primitive_slug: "avg-seats-per-carrier-addressable",
          primitive_name: "Avg addressable IT seats / carrier",
          value: 350,
          unit_label: "seats/carrier",
        },
        {
          role: "conditional_adjustment",
          primitive_slug: "pct-addressable-by-doc-gen",
          primitive_name: "% of seats addressable by doc-gen",
          value: 0.4,
          unit_label: "%",
        },
        {
          role: "base_value",
          primitive_slug: "avg-acv-per-seat",
          primitive_name: "Avg ACV / seat",
          value: 480,
          unit_label: "$/seat/yr",
        },
        {
          role: "conditional_adjustment",
          primitive_slug: "mature-penetration",
          primitive_name: "Mature penetration",
          value: 0.25,
          unit_label: "%",
        },
      ],
    },
    {
      definition: "Top-down from P&C IT spend",
      value: 213_000_000,
      unit_label: "$/yr",
      framework_slug: "top-down-from-pc-it-spend",
      framework_name: "Top-down from P&C IT spend",
      method_family: "top_down_spend",
      inputs_used: [
        {
          role: "base_value",
          primitive_slug: "pc-it-spend-us",
          primitive_name: "US P&C carrier IT spend",
          value: 14_200_000_000,
          unit_label: "$/yr",
        },
        {
          role: "conditional_adjustment",
          primitive_slug: "share-it-on-doc-automation",
          primitive_name: "% of IT spend on doc automation",
          value: 0.015,
          unit_label: "%",
        },
      ],
    },
    {
      definition: "Analog from doc-gen in adjacent verticals",
      value: 80_000_000,
      unit_label: "$/yr",
      framework_slug: "analog-doc-gen-adjacent-verticals",
      framework_name: "Analog from adjacent vertical doc-gen TAMs",
      method_family: "analog_penetration",
      inputs_used: [
        {
          role: "base_value",
          primitive_slug: "us-healthcare-doc-gen-tam",
          primitive_name: "US healthcare doc-gen TAM",
          value: 450_000_000,
          unit_label: "$/yr",
        },
        {
          role: "conditional_adjustment",
          primitive_slug: "pc-vs-healthcare-doc-ratio",
          primitive_name: "P&C / healthcare claims-doc ratio",
          value: 0.18,
          unit_label: "ratio",
        },
      ],
    },
  ],
  triangulated_range: { low: 11_000_000, high: 497_000_000 },
  independence_score: 0.78,
  method_families_used: ["bottoms_up_seats", "top_down_spend", "analog_penetration"],
  uses_synthetic_primitives: false,
  uses_modeled_composites: true,
};

const INTERPRETATIONS_BY_QUERY: Record<string, Interpretation[]> = {
  default: [
    {
      label: "Doc-gen tooling for P&C insurance carriers, US",
      narrow_or_broad: "default",
      concept_slug: "pc-doc-gen-tam-us",
      constraints: {
        qualitative: "Doc-gen, enterprise IT",
        quantitative: "Enterprise carriers",
        industry: "P&C insurance",
        geo: "US",
      },
      preview_range: { low: 11_000_000, high: 497_000_000 },
    },
  ],
};

const INTERPRETATION_BY_CONCEPT: Record<string, BuildResponse> = {
  "pc-doc-gen-tam-us": PC_DOC_GEN_BUILD,
};

export async function parseQuery(query: string): Promise<Interpretation[]> {
  // Wire to real LLM parser (v0.3.2). For now we return the only seeded interpretation.
  if (!query.trim()) return [];
  return INTERPRETATIONS_BY_QUERY.default;
}

export async function getBuild(conceptSlug: string): Promise<BuildResponse> {
  const build = INTERPRETATION_BY_CONCEPT[conceptSlug];
  if (!build) {
    throw new Error(`No build seeded for concept "${conceptSlug}"`);
  }
  return build;
}

export function formatUSD(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

export function tierLabel(tier: SourceTier): string {
  return tier
    .split("_")
    .map((s) => s[0]?.toUpperCase() + s.slice(1))
    .join(" ");
}
