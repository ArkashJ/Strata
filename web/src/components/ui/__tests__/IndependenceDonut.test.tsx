import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IndependenceDonut } from "../IndependenceDonut";

describe("IndependenceDonut", () => {
  it("renders the score to two decimals in the center", () => {
    render(<IndependenceDonut score={0.5} />);
    expect(screen.getByText("0.50")).toBeInTheDocument();
  });

  it("shows the INDEPENDENCE eyebrow", () => {
    render(<IndependenceDonut score={0.5} />);
    expect(screen.getByText(/independence/i)).toBeInTheDocument();
  });

  it("clamps out-of-range scores into 0–1", () => {
    render(<IndependenceDonut score={1.8} />);
    expect(screen.getByText("1.00")).toBeInTheDocument();
  });

  it("clamps negatives to 0", () => {
    render(<IndependenceDonut score={-0.4} />);
    expect(screen.getByText("0.00")).toBeInTheDocument();
  });

  it("exposes an accessible label on the gauge", () => {
    render(<IndependenceDonut score={0.73} />);
    expect(screen.getByLabelText(/0\.73 out of 1/)).toBeInTheDocument();
  });

  it("draws the arc with the accent token, not a hex", () => {
    const { container } = render(<IndependenceDonut score={0.6} />);
    const arc = container.querySelectorAll("circle")[1];
    expect(arc.getAttribute("stroke")).toBe("var(--accent)");
  });
});
