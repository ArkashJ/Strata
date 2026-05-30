/** Wave 2 / AC2.2 — pyramid context menu + ghost card presentation. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PyramidNode } from "@/lib/pyramid";
import {
  GhostCard,
  type MenuAnchor,
  NodeContextMenu,
  PYRAMID_MENU_ITEMS,
} from "../PyramidOverlays";

const NODE: PyramidNode = {
  id: "industry:demo-ai-dev-tooling-us",
  pillar: "industry",
  key: "demo-ai-dev-tooling-us",
  label: "AI developer tooling",
  weight: 7,
};
const ANCHOR: MenuAnchor = { node: NODE, x: 100, y: 120 };

describe("NodeContextMenu", () => {
  it("renders the three locked actions and fires onAction", () => {
    const onAction = vi.fn();
    const onClose = vi.fn();
    render(<NodeContextMenu anchor={ANCHOR} onAction={onAction} onClose={onClose} />);

    for (const item of PYRAMID_MENU_ITEMS) {
      expect(screen.getByRole("menuitem", { name: item.label })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("menuitem", { name: "Suggest framework" }));
    expect(onAction).toHaveBeenCalledWith("framework", NODE);
    expect(onClose).toHaveBeenCalled();
  });
});

describe("GhostCard", () => {
  it("shows the node label, pillar, and weight", () => {
    render(<GhostCard anchor={ANCHOR} />);
    const card = screen.getByTestId("pyramid-ghost-card");
    expect(card).toHaveTextContent("AI developer tooling");
    expect(card).toHaveTextContent("weight 7");
  });
});
