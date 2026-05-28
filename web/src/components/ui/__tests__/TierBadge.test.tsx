import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TierBadge } from "../TierBadge";

describe("TierBadge", () => {
  it("renders an uppercase tier label", () => {
    render(<TierBadge tier="regulator" />);
    // Label text is title-cased; CSS uppercases it visually.
    expect(screen.getByText("Regulator")).toBeInTheDocument();
  });

  it("carries the raw tier on a data attribute", () => {
    const { container } = render(<TierBadge tier="prediction_market" />);
    expect(container.querySelector('[data-tier="prediction_market"]')).not.toBeNull();
  });

  it("folds analyst-paraphrase onto the analyst palette", () => {
    const { container } = render(<TierBadge tier="analyst-paraphrase" />);
    const el = container.querySelector("span");
    expect(el?.getAttribute("style")).toContain("var(--tier-analyst-tint)");
  });

  it("renders without hardcoded hex colors", () => {
    const { container } = render(<TierBadge tier="first_party" />);
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });
});
