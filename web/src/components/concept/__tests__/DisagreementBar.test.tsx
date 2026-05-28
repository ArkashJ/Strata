import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AtomicPrimitive, CompositePrimitive, PrimitiveDetail } from "@/lib/schemas";
import { type DisagreementRow, DisagreementView, toRows } from "../DisagreementBar";

function atomic(over: Partial<AtomicPrimitive>): AtomicPrimitive {
  return {
    kind: "atomic_primitive",
    slug: "p1",
    schema_version: 1,
    concept_slug: "c1",
    name: "Measurement one",
    description: "",
    value: 100,
    unit: { kind: "stock", dimension: "people", basis: "nominal" },
    as_of: "2024-05-31",
    geo: { level: "country", codes: ["US"] },
    geo_perspective: "supply",
    distribution_shape: "normal",
    delivery_mode: "n/a",
    source: {
      slug: "s1",
      url: "https://example.gov",
      accessed: "2026-01-01",
      snapshot_sha256: "abc",
      tier: "regulator",
    },
    derives_from: [],
    ...over,
  };
}

function composite(): CompositePrimitive {
  return {
    kind: "composite_primitive",
    slug: "comp1",
    schema_version: 1,
    concept_slug: "c1",
    name: "Composite",
    description: "",
    inputs: ["p1"],
    set_operation: "union",
    as_of: "2024-05-31",
    unit: { kind: "stock", dimension: "people", basis: "nominal" },
    geo: { level: "country", codes: ["US"] },
    geo_perspective: "supply",
  };
}

describe("toRows", () => {
  it("keeps atomic primitives and drops composites (no comparable scalar)", () => {
    const measurements: PrimitiveDetail[] = [
      atomic({ slug: "a", name: "A", value: 10 }),
      composite(),
      atomic({ slug: "b", name: "B", value: 20 }),
    ];
    const rows = toRows(measurements);
    expect(rows.map((r) => r.slug)).toEqual(["a", "b"]);
    expect(rows[0]).toMatchObject({ value: 10, tier: "regulator" });
  });
});

describe("DisagreementView", () => {
  const rows: DisagreementRow[] = [
    {
      slug: "a",
      name: "Survey A",
      value: 100,
      tier: "regulator",
      asOf: "2024-01-01",
      unit: { kind: "stock", dimension: "people", basis: "nominal" },
    },
    {
      slug: "b",
      name: "Survey B",
      value: 300,
      tier: "analyst",
      asOf: "2024-06-01",
      unit: { kind: "stock", dimension: "people", basis: "nominal" },
    },
  ];

  it("renders a measurement count with the spread subtitle", () => {
    render(<DisagreementView rows={rows} />);
    // 2 measurements, spread = 300 - 100 = 200 → compact "200".
    expect(screen.getByText(/2 measurements/)).toBeInTheDocument();
    expect(screen.getByText(/spread/)).toBeInTheDocument();
  });

  it("exposes a STACKED · TABLE · TIME SERIES toggle", () => {
    render(<DisagreementView rows={rows} />);
    expect(screen.getByRole("tab", { name: "STACKED" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "TABLE" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "TIME SERIES" })).toBeInTheDocument();
  });

  it("renders each measurement name as a bar row", () => {
    render(<DisagreementView rows={rows} />);
    expect(screen.getByText("Survey A")).toBeInTheDocument();
    expect(screen.getByText("Survey B")).toBeInTheDocument();
  });
});
