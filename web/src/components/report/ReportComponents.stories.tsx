/**
 * Report component system — the Coatue/Gartner-caliber visual blocks, each in
 * empty / populated (and where relevant error/dense) states. Storybook needs no
 * app auth, so this is the fast visual loop for the report look before wiring it
 * into the gated /tam/<hash>/report page.
 *
 * The decorator gives each story a paper-width canvas so the blocks read at
 * report scale, not centered-widget scale.
 */
import type { Meta, StoryObj } from "@storybook/react";

import { ComparisonTable } from "./ComparisonTable";
import { HexCapabilityMap } from "./HexCapabilityMap";
import { KpiStrip } from "./KpiStrip";
import { MarketAreaChart } from "./MarketAreaChart";
import { PenetrationCurve } from "./PenetrationCurve";
import { QuadrantScatter } from "./QuadrantScatter";
import { RankedBarDistribution } from "./RankedBarDistribution";
import { ReportHeadline } from "./ReportHeadline";
import { SourceAppendixTable } from "./SourceAppendixTable";
import { StackedBridge } from "./StackedBridge";
import { TriangulationPanel } from "./TriangulationPanel";

const meta = {
  title: "Report/Components",
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <div style={{ width: "min(860px, 92vw)", margin: "0 auto", padding: "1rem" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta;

export default meta;
type Story = StoryObj;

const USD = { kind: "money", dimension: "currency", currency: "USD" } as const;

// ── ReportHeadline ──────────────────────────────────────────────────────────

export const Headline: Story = {
  name: "ReportHeadline / populated",
  render: () => (
    <ReportHeadline
      eyebrow="Executive summary"
      headline="AI inference accelerators are a $58B market by 2027"
      subtitle="Total addressable market · USD nominal · 2 independent methods"
      source="source: blended top-down + bottoms-up · permalink /tam/a1b2c3d4e5f6"
    >
      <KpiStrip
        items={[
          { label: "Triangulated TAM", value: "$58.0B", emphasis: true },
          { label: "Range", value: "$41.2B – $74.8B" },
          { label: "Methods", value: "2" },
          { label: "Independence", value: "0.86" },
        ]}
      />
    </ReportHeadline>
  ),
};

export const HeadlineNoSource: Story = {
  name: "ReportHeadline / no source (honesty fence)",
  render: () => (
    <ReportHeadline
      headline="A market with no composable source string"
      subtitle="The footnote renders nothing rather than fabricate provenance"
      source={null}
    >
      <KpiStrip items={[{ label: "TAM", value: "$12.0B", emphasis: true }]} />
    </ReportHeadline>
  ),
};

// ── KpiStrip ──────────────────────────────────────────────────────────────────

export const Kpis: Story = {
  name: "KpiStrip / populated",
  render: () => (
    <KpiStrip
      items={[
        { label: "Triangulated TAM", value: "$58.0B", emphasis: true, note: "leans modeled" },
        { label: "Range", value: "$41.2B – $74.8B" },
        { label: "Methods", value: "2" },
        { label: "Independence", value: "0.86" },
      ]}
    />
  ),
};

export const KpisEmpty: Story = {
  name: "KpiStrip / empty",
  render: () => <KpiStrip items={[]} />,
};

// ── PenetrationCurve ──────────────────────────────────────────────────────────

const ADOPTION = Array.from({ length: 26 }, (_, year) => ({
  x: year,
  AI: Math.min(0.92, 1 - Math.exp(-year / 3)),
  Internet: Math.min(0.92, year < 6 ? year * 0.02 : 0.1 + (year - 6) * 0.04),
  PCs: Math.min(0.88, year < 8 ? year * 0.015 : 0.1 + (year - 8) * 0.035),
}));

export const Penetration: Story = {
  name: "PenetrationCurve / populated (Coatue S-curve)",
  render: () => (
    <PenetrationCurve
      headline="AI is still early in its journey but massive adoption so far"
      subtitle="US % penetration · years since first major launch"
      data={ADOPTION}
      todayX={3}
      series={[
        { key: "AI", label: "AI", annotation: "MAUs of ChatGPT" },
        { key: "Internet", label: "Internet", annotation: "broadband users" },
        { key: "PCs", label: "PCs", annotation: "personal computer users" },
      ]}
      source="illustrative analog curves — sourced primitives required before citing"
    />
  ),
};

export const PenetrationEmpty: Story = {
  name: "PenetrationCurve / empty",
  render: () => <PenetrationCurve headline="Adoption curve" data={[]} series={[]} source={null} />,
};

// ── MarketAreaChart ───────────────────────────────────────────────────────────

const GDP_SHARE = Array.from({ length: 36 }, (_, i) => {
  const yr = 1990 + i;
  const base = 0.1 + 0.005 * i + 0.06 * Math.sin(i / 4);
  return { x: yr, value: Math.max(0.05, yr >= 2024 ? base + 0.25 : base) };
});

export const Area: Story = {
  name: "MarketAreaChart / populated (cap as % GDP)",
  render: () => (
    <MarketAreaChart
      headline="AI leaders are too big"
      subtitle="Market cap for top 10 companies as % of US GDP"
      data={GDP_SHARE}
      valueLabel="% of US GDP"
      yTickFormat={(v) => `${Math.round(v * 100)}%`}
      peaks={[
        { x: 2000, label: "34%" },
        { x: 2025, label: "77%" },
      ]}
      source="illustrative — sourced market-cap & GDP primitives required before citing"
    />
  ),
};

export const AreaEmpty: Story = {
  name: "MarketAreaChart / empty",
  render: () => (
    <MarketAreaChart headline="Cap as % of GDP" data={[]} valueLabel="%" source={null} />
  ),
};

// ── RankedBarDistribution ─────────────────────────────────────────────────────

export const Ranked: Story = {
  name: "RankedBarDistribution / populated (Gartner scores)",
  render: () => (
    <RankedBarDistribution
      headline="How the methods compare"
      subtitle="Each method's estimate, ranked"
      max={75}
      rows={[
        { label: "Top-down · spend", value: 74.8, display: "$74.8B" },
        { label: "Comparable revenue", value: 58.0, display: "$58.0B" },
        { label: "Bottoms-up · seats", value: 41.2, display: "$41.2B" },
      ]}
      source="source: 3 method families · /tam/a1b2c3d4e5f6"
    />
  ),
};

export const RankedTier: Story = {
  name: "RankedBarDistribution / coloured by tier",
  render: () => (
    <RankedBarDistribution
      headline="Inputs by source tier"
      colorBy="tier"
      rows={[
        { label: "US labor headcount", value: 8, display: "8.2M", tier: "regulator" },
        { label: "Sector spend", value: 6, display: "$6.1B", tier: "aggregator" },
        { label: "Analyst ACV", value: 4, display: "$42K", tier: "analyst" },
        { label: "Modeled adoption", value: 3, display: "30%", tier: "community-modeled" },
      ]}
    />
  ),
};

export const RankedEmpty: Story = {
  name: "RankedBarDistribution / empty",
  render: () => <RankedBarDistribution rows={[]} headline="Ranking" />,
};

// ── ComparisonTable ───────────────────────────────────────────────────────────

export const Comparison: Story = {
  name: "ComparisonTable / populated (competitive landscape)",
  render: () => (
    <ComparisonTable
      headline="Competitive landscape"
      subtitle="Named players, by inference-accelerator revenue share"
      rows={[
        { key: "nvidia", label: "NVIDIA", value: 72, display: "72%" },
        { key: "amd", label: "AMD", value: 11, display: "11%" },
        { key: "broadcom", label: "Broadcom", value: 8, display: "8%", note: "custom silicon" },
        {
          key: "hyperscaler",
          label: "Hyperscaler silicon",
          value: 9,
          display: "9%",
          note: "TPU/Trainium",
        },
      ]}
      insight={{
        title: "One vendor holds ~3/4 of the market",
        body: "Concentration this high makes the top-down spend method sensitive to a single ASP assumption.",
      }}
      source="illustrative shares — sourced competitor primitives required before citing"
    />
  ),
};

export const ComparisonEmpty: Story = {
  name: "ComparisonTable / empty",
  render: () => <ComparisonTable rows={[]} headline="Competitive landscape" />,
};

// ── StackedBridge ─────────────────────────────────────────────────────────────

export const Bridge: Story = {
  name: "StackedBridge / populated (factor chain → TAM)",
  render: () => (
    <StackedBridge
      headline="How the number builds"
      subtitle="latent_demand · population × adoption × WTP"
      steps={[
        { label: "Target population", factor: 12_000_000, display: "12.0M", tier: "regulator" },
        { label: "Adoption rate", factor: 0.3, display: "30%", tier: "community-modeled" },
        { label: "Willingness to pay", factor: 16_100, display: "$16.1K", tier: "analyst" },
      ]}
      total={57_960_000_000}
      totalDisplay="$58.0B"
      source="source: BLS headcount · analyst ACV · modeled adoption"
    />
  ),
};

export const BridgeEmpty: Story = {
  name: "StackedBridge / empty",
  render: () => <StackedBridge steps={[]} total={0} totalDisplay="—" headline="How it builds" />,
};

// ── HexCapabilityMap ──────────────────────────────────────────────────────────

export const Hex: Story = {
  name: "HexCapabilityMap / populated (Gartner honeycomb)",
  render: () => (
    <HexCapabilityMap
      headline="What a modern market-intelligence platform does"
      center={{ label: "Discover sourced numbers", weight: 1 }}
      satellites={[
        { label: "Verify claims", weight: 0.9 },
        { label: "Triangulate methods", weight: 0.8 },
        { label: "Drill to source", weight: 0.85 },
        { label: "Recompute live", weight: 0.6 },
        { label: "Sensitivity", weight: 0.5 },
        { label: "Contribution flywheel", weight: 0.2 },
      ]}
      source="capability map — qualitative, not a quantitative chart"
    />
  ),
};

export const HexGaps: Story = {
  name: "HexCapabilityMap / with gaps",
  render: () => (
    <HexCapabilityMap
      headline="Coverage with honest gaps"
      center={{ label: "Core", weight: 1 }}
      satellites={[
        { label: "Built", weight: 0.9 },
        { label: "Built", weight: 0.7 },
        { label: "Gap" },
        { label: "Gap" },
        { label: "Partial", weight: 0.3 },
        { label: "Built", weight: 0.6 },
      ]}
    />
  ),
};

// ── QuadrantScatter ───────────────────────────────────────────────────────────

export const Quadrant: Story = {
  name: "QuadrantScatter / populated (magic quadrant)",
  render: () => (
    <QuadrantScatter
      headline="Sourcing depth vs method breadth"
      xLabel="Completeness of execution"
      yLabel="Ability to source"
      quadrantLabels={["Niche", "Challengers", "Visionaries", "Leaders"]}
      points={[
        { label: "Strata", x: 0.82, y: 0.88 },
        { label: "Legacy report", x: 0.35, y: 0.6 },
        { label: "Raw LLM", x: 0.7, y: 0.15 },
        { label: "Spreadsheet", x: 0.2, y: 0.3 },
      ]}
      source="illustrative positioning — not a scored vendor evaluation"
    />
  ),
};

export const QuadrantEmpty: Story = {
  name: "QuadrantScatter / empty",
  render: () => (
    <QuadrantScatter headline="Positioning" xLabel="x" yLabel="y" points={[]} source={null} />
  ),
};

// ── TriangulationPanel ────────────────────────────────────────────────────────

export const Triangulation: Story = {
  name: "TriangulationPanel / converged",
  render: () => (
    <TriangulationPanel
      convergence={{
        low_family: "bottoms_up_seats",
        high_family: "top_down_spend",
        low_value: 41_200_000_000,
        high_value: 74_800_000_000,
        ratio: 1.82,
        unit: USD,
      }}
    />
  ),
};

export const TriangulationSingle: Story = {
  name: "TriangulationPanel / single method (honest gap)",
  render: () => (
    <TriangulationPanel
      convergence={null}
      singleMethod={{ family: "top_down_spend", value: 58_000_000_000, unit: USD }}
    />
  ),
};

// ── SourceAppendixTable ───────────────────────────────────────────────────────

export const Appendix: Story = {
  name: "SourceAppendixTable / populated",
  render: () => (
    <SourceAppendixTable
      rows={[
        {
          role_name: "population",
          role: "base_value",
          primitive_slug: "bls-soc-15-1252-headcount",
          snapshot_sha256: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
          value: 12_000_000,
          name: "US software developers",
          unit: { kind: "count", dimension: "count" },
          source_tier: "regulator",
          source_url: "https://www.bls.gov/oes/",
          as_of: "2024-05-01",
        },
        {
          role_name: "acv",
          role: "base_value",
          primitive_slug: "analyst-acv-ai-tools",
          snapshot_sha256: "d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3d3",
          value: 16_100,
          name: "Analyst ACV estimate",
          unit: USD,
          source_tier: "analyst",
          source_url: "https://example.com/analyst-note",
          as_of: "2025-01-15",
        },
        {
          role_name: "adoption",
          role: "regime_modifier",
          primitive_slug: "modeled-adoption-2027",
          snapshot_sha256: "",
          value: 0.3,
          name: "Modeled adoption (2027)",
          unit: { kind: "ratio", dimension: "ratio" },
          source_tier: "community-modeled",
          source_url: null,
          as_of: null,
        },
      ]}
    />
  ),
};

export const AppendixEmpty: Story = {
  name: "SourceAppendixTable / empty",
  render: () => <SourceAppendixTable rows={[]} />,
};
