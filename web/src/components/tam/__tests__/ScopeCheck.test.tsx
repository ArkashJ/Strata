/** Sub-project 1 — the scope-check surface on the /tam artifact. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MarketScope, ScopeReport } from "@/lib/schemas";
import { ScopeRailSummary, ScopeStrip, ScopeWarnings } from "../ScopeCheck";

const EMPTY_SCOPE: MarketScope = {
  vertical: [],
  persona: [],
  segment: null,
  geo_supply: [],
  geo_demand: [],
  product: [],
  include: [],
  exclude: [],
};

const DECLARED: MarketScope = {
  ...EMPTY_SCOPE,
  persona: [
    { system: "SOC", code: "41-3000", label: "Sales representatives, services" },
    { system: "SOC", code: "41-4000", label: "Sales representatives, wholesale & manufacturing" },
  ],
  segment: { min_emp: null, max_emp: null, label: "All employer firms" },
  geo_demand: ["US"],
};

const REPORT: ScopeReport = {
  declared: DECLARED,
  ok: false,
  inputs: [
    {
      primitive_slug: "demo-bls-sales-reps-us-2024",
      role_name: "persona_pool",
      displayed: {
        ...EMPTY_SCOPE,
        persona: [{ system: "SOC", code: "41-4012", label: "Sales reps, wholesale & mfg" }],
        geo_demand: ["US"],
      },
      warnings: [
        {
          dimension: "persona",
          relationship: "narrower",
          message: "Source covers SOC 41-4012 — narrower. Excludes SOC 41-3000 entirely.",
        },
      ],
    },
    {
      primitive_slug: "demo-ai-sales-ops-acv-per-seat-2024",
      role_name: "cost_per_persona",
      displayed: { ...EMPTY_SCOPE, product: ["ai-sales-ops-tooling"], geo_demand: ["US"] },
      warnings: [],
    },
  ],
};

describe("ScopeStrip", () => {
  it("renders the declared market as chips, nothing when empty", () => {
    render(<ScopeStrip scope={DECLARED} />);
    const strip = screen.getByTestId("scope-strip");
    expect(strip).toHaveTextContent("41-3000");
    expect(strip).toHaveTextContent("All employer firms");
    expect(strip).toHaveTextContent("US");
  });

  it("renders nothing for an empty scope", () => {
    render(<ScopeStrip scope={EMPTY_SCOPE} />);
    expect(screen.queryByTestId("scope-strip")).toBeNull();
  });
});

describe("ScopeWarnings", () => {
  it("lists only flagged inputs and names the relationship + excluded group", () => {
    render(<ScopeWarnings report={REPORT} />);
    const block = screen.getByTestId("scope-check");
    expect(block).toHaveTextContent(/narrower/i);
    expect(block).toHaveTextContent("Excludes SOC 41-3000 entirely");
    // the clean price input must NOT appear as a warning row
    expect(block).not.toHaveTextContent("cost_per_persona");
    expect(block).toHaveTextContent("persona_pool");
  });

  it("shows an all-clear message when ok", () => {
    render(<ScopeWarnings report={{ ...REPORT, ok: true, inputs: [] }} />);
    expect(screen.getByTestId("scope-check")).toHaveTextContent(/matches the declared market/i);
  });
});

describe("ScopeRailSummary", () => {
  it("counts off-scope inputs", () => {
    render(<ScopeRailSummary report={REPORT} />);
    expect(screen.getByText(/1 input off-scope/i)).toBeInTheDocument();
  });
});
