/**
 * PremiumReport — the full Coatue/Gartner report composition rendered from a
 * mock TAMOutput. Stories cover: a triangulated TAM with sensitivity +
 * competitive + adoption payload (the "complete" report), a bare TAM (every
 * optional section degrades to an honest gap), and a single-method TAM (the
 * triangulation panel states the missing direction). No app auth needed.
 */
import type { Meta, StoryObj } from "@storybook/react";

import type { SensitivityResponse } from "@/components/charts/TornadoChart";
import type { Scenario, TAMOutput, Unit } from "@/lib/schemas";
import { PremiumReport, type PremiumReportPayload } from "./PremiumReport";

const USD: Unit = { kind: "money", dimension: "currency", currency: "USD" };
const COUNT: Unit = { kind: "count", dimension: "count" };
const RATIO: Unit = { kind: "ratio", dimension: "ratio" };

function scenario(over: Partial<Scenario>): Scenario {
  return {
    definition: "AI inference accelerators · US + global · 2027",
    lens: "latent_demand",
    framework: "latent-demand-v1",
    framework_variant: null,
    value: 58_000_000_000,
    unit: USD,
    inputs_used: [],
    assumptions: {},
    banners: [],
    ...over,
  };
}

const TOP_DOWN = scenario({
  framework: "top-down-spend",
  lens: "revenue_generation",
  value: 74_800_000_000,
  inputs_used: [
    {
      role_name: "sector_spend",
      role: "base_value",
      primitive_slug: "aggregator-ai-hardware-spend",
      snapshot_sha256: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
      value: 220_000_000_000,
      name: "Global AI hardware spend",
      unit: USD,
      source_tier: "aggregator",
      source_url: "https://example.com/idc",
    },
    {
      role_name: "accelerator_share",
      role: "conditional_adjustment",
      primitive_slug: "analyst-accelerator-share",
      snapshot_sha256: "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
      value: 0.34,
      name: "Accelerator share of spend",
      unit: RATIO,
      source_tier: "analyst",
      source_url: "https://example.com/analyst",
    },
  ],
});

const BOTTOMS_UP = scenario({
  framework: "bottoms-up-seats",
  lens: "latent_demand",
  value: 41_200_000_000,
  inputs_used: [
    {
      role_name: "population",
      role: "base_value",
      primitive_slug: "bls-datacenter-gpu-count",
      snapshot_sha256: "c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
      value: 8_000_000,
      name: "Installed accelerator base",
      unit: COUNT,
      source_tier: "regulator",
      source_url: "https://www.census.gov/",
    },
    {
      role_name: "adoption",
      role: "regime_modifier",
      primitive_slug: "modeled-refresh-rate",
      snapshot_sha256: "",
      value: 0.35,
      name: "Annual refresh rate (modeled)",
      unit: RATIO,
      source_tier: "community-modeled",
      source_url: null,
    },
    {
      role_name: "asp",
      role: "base_value",
      primitive_slug: "analyst-accelerator-asp",
      snapshot_sha256: "d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3",
      value: 14_700,
      name: "Accelerator ASP",
      unit: USD,
      source_tier: "analyst",
      source_url: "https://example.com/asp",
    },
  ],
});

const TRIANGULATED: TAMOutput = {
  kind: "tam_output",
  state_hash: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
  schema_version: 2,
  created_by: "demo",
  created_at: "2026-06-07T00:00:00Z",
  target: {
    concept: "ai-inference-accelerators",
    concept_name: "AI inference accelerators",
    geo: "US+global",
    time: "2027",
    expansion_stage: "current",
  },
  scenarios: [TOP_DOWN, BOTTOMS_UP],
  method_families_used: ["top_down_spend", "bottoms_up_seats"],
  convergence: {
    low_family: "bottoms_up_seats",
    high_family: "top_down_spend",
    low_value: 41_200_000_000,
    high_value: 74_800_000_000,
    ratio: 1.82,
    unit: USD,
  },
  independence_score: 0.86,
  uses_synthetic_primitives: false,
  uses_modeled_composites: true,
  scope: null,
};

const SINGLE: TAMOutput = {
  ...TRIANGULATED,
  state_hash: "deadbeefdeadbeefdeadbeefdeadbeef",
  scenarios: [TOP_DOWN],
  method_families_used: ["top_down_spend"],
  convergence: null,
  uses_modeled_composites: false,
};

const SENSITIVITY: SensitivityResponse = {
  concept_slug: "ai-inference-accelerators",
  base: 58_000_000_000,
  pct: 0.2,
  inputs: [
    {
      primitive_slug: "analyst-accelerator-share",
      name: "Accelerator share of spend",
      base: 0.34,
      low: 46_400_000_000,
      high: 69_600_000_000,
      impact: 23_200_000_000,
    },
    {
      primitive_slug: "modeled-refresh-rate",
      name: "Annual refresh rate (modeled)",
      base: 0.35,
      low: 49_300_000_000,
      high: 66_700_000_000,
      impact: 17_400_000_000,
    },
    {
      primitive_slug: "analyst-accelerator-asp",
      name: "Accelerator ASP",
      base: 14_700,
      low: 52_200_000_000,
      high: 63_800_000_000,
      impact: 11_600_000_000,
    },
  ],
};

const FULL_PAYLOAD: PremiumReportPayload = {
  sensitivity: SENSITIVITY,
  competitive: {
    valueLabel: "Inference-accelerator revenue share",
    rows: [
      { key: "nvidia", label: "NVIDIA", value: 72, display: "72%" },
      { key: "amd", label: "AMD", value: 11, display: "11%" },
      { key: "broadcom", label: "Broadcom", value: 8, display: "8%", note: "custom silicon" },
      { key: "hyperscaler", label: "Hyperscaler silicon", value: 9, display: "9%" },
    ],
    insight: {
      title: "One vendor holds ~3/4 of the market",
      body: "Concentration this high makes the top-down spend method sensitive to a single ASP assumption.",
    },
    source: "illustrative shares — sourced competitor primitives required before citing",
  },
  penetration: {
    todayX: 3,
    data: Array.from({ length: 16 }, (_, year) => ({
      x: year,
      AI: Math.min(0.92, 1 - Math.exp(-year / 3)),
      Internet: Math.min(0.92, year < 6 ? year * 0.04 : 0.24 + (year - 6) * 0.05),
    })),
    series: [
      { key: "AI", label: "AI", annotation: "MAUs of inference" },
      { key: "Internet", label: "Internet", annotation: "analog adoption" },
    ],
    source: "illustrative analog curves — sourced primitives required before citing",
  },
};

const meta = {
  title: "Report/PremiumReport",
  component: PremiumReport,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <div style={{ width: "min(900px, 94vw)", margin: "0 auto", padding: "1.5rem 1rem" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PremiumReport>;

export default meta;
type Story = StoryObj<typeof PremiumReport>;

export const Complete: Story = {
  name: "Complete (triangulated + full payload)",
  args: { tam: TRIANGULATED, payload: FULL_PAYLOAD },
};

export const BareTam: Story = {
  name: "Bare TAM (optional sections degrade to honest gaps)",
  args: { tam: TRIANGULATED, payload: undefined },
};

export const SingleMethod: Story = {
  name: "Single method (triangulation states the gap)",
  args: { tam: SINGLE, payload: { sensitivity: SENSITIVITY } },
};
