/** Wave 5C / AC5C.1 — BrandIcon renders known marks + never crashes on unknown. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrandIcon } from "../BrandIcon";
import { brandMark, monogram } from "../brand-registry";

// Marks present in simple-icons v16 (Slack/Salesforce/Segment were removed
// upstream for brand reasons; they correctly fall back to a monogram).
const VENDORS = [
  "GitHub",
  "Gmail",
  "Notion",
  "Jira",
  "Linear",
  "HubSpot",
  "Snowflake",
  "Stripe",
  "QuickBooks",
  "Google Sheets",
  "Airtable",
  "Anthropic",
];

describe("brand-registry", () => {
  it("resolves a real SVG path for known vendors", () => {
    for (const v of VENDORS) {
      const mark = brandMark(v);
      expect(mark, `${v} should have a mark`).not.toBeNull();
      expect(mark?.path.length).toBeGreaterThan(10);
    }
  });

  it("returns null for unknown names + upstream-removed marks (fall back)", () => {
    expect(brandMark("totally-unknown-vendor")).toBeNull();
    expect(brandMark("Slack")).toBeNull(); // removed from simple-icons v16
    expect(monogram("World Bank")).toBe("WB");
  });
});

describe("BrandIcon", () => {
  it("renders a known vendor without crashing", () => {
    render(<BrandIcon name="GitHub" />);
    expect(screen.getByLabelText("GitHub")).toBeInTheDocument();
  });

  it("falls back to a monogram for a gov source / unknown name", () => {
    render(<BrandIcon name="BLS" />);
    expect(screen.getByLabelText("BLS")).toHaveTextContent("BL");
  });
});
