/**
 * Chart gallery — every reusable chart type rendered with sample data, themed
 * through the --chart-* tokens. Storybook needs no app auth, so this is the fast
 * loop for iterating on chart visuals before wiring them into a gated page.
 */
import type { Meta, StoryObj } from "@storybook/react";

import { DonutChart } from "./DonutChart";
import { RadarChart } from "./RadarChart";
import { RadialChart } from "./RadialChart";

const meta = {
  title: "Charts/Gallery",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj;

const SLICES = [
  { label: "Top-down", value: 31.2 },
  { label: "Bottoms-up", value: 2.0 },
  { label: "Analyst", value: 12.4 },
  { label: "Modeled", value: 7.8 },
];

export const Donut: Story = {
  name: "Donut / Pie",
  render: () => (
    <div style={{ width: 320 }}>
      <DonutChart data={SLICES} centerValue="$53.4B" centerLabel="blended TAM" />
    </div>
  ),
};

export const Radial: Story = {
  name: "Radial bar",
  render: () => (
    <div style={{ width: 320 }}>
      <RadialChart data={SLICES} />
    </div>
  ),
};

export const Radar: Story = {
  name: "Radar / spider",
  render: () => (
    <div style={{ width: 360 }}>
      <RadarChart
        data={[
          { axis: "Sourcing", "AI sales": 8, Incumbents: 5 },
          { axis: "Coverage", "AI sales": 6, Incumbents: 9 },
          { axis: "Freshness", "AI sales": 9, Incumbents: 4 },
          { axis: "Defensibility", "AI sales": 7, Incumbents: 8 },
          { axis: "Cost", "AI sales": 9, Incumbents: 3 },
        ]}
        series={["AI sales", "Incumbents"]}
      />
    </div>
  ),
};
