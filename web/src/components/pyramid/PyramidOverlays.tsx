"use client";

// Pyramid interaction overlays (Wave 2 / AC2.2): a right-click context menu and
// a 250ms hover-intent ghost card. Kept presentational + pure so the menu action
// set and the card content are unit-testable without driving ReactFlow.
import { PILLAR_LABEL, type PyramidNode } from "@/lib/pyramid";

export interface MenuAnchor {
  node: PyramidNode;
  x: number;
  y: number;
}

export interface ContextMenuItem {
  key: string;
  label: string;
}

// The locked U1 right-click actions (Q11): expand children, suggest a fitting
// framework, annotate. Exported so a test can assert the action set.
export const PYRAMID_MENU_ITEMS: ContextMenuItem[] = [
  { key: "expand", label: "Expand children" },
  { key: "framework", label: "Suggest framework" },
  { key: "annotate", label: "Annotate" },
];

export function NodeContextMenu({
  anchor,
  onAction,
  onClose,
}: {
  anchor: MenuAnchor;
  onAction: (key: string, node: PyramidNode) => void;
  onClose: () => void;
}) {
  return (
    <>
      {/* Click-away catcher. */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(e) => e.preventDefault()}
      />
      <ul
        role="menu"
        aria-label="Node actions"
        className="fixed z-50 min-w-[180px] overflow-hidden rounded-[var(--r-2)] border border-[var(--card-border)] bg-[var(--bg-1)] py-1 shadow-[var(--card-shadow)]"
        style={{ left: anchor.x, top: anchor.y }}
      >
        <li className="px-3 py-1.5 text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)] truncate">
          {anchor.node.label}
        </li>
        {PYRAMID_MENU_ITEMS.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              role="menuitem"
              className="w-full px-3 py-1.5 text-left text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)]"
              onClick={() => {
                onAction(item.key, anchor.node);
                onClose();
              }}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

export function GhostCard({ anchor }: { anchor: MenuAnchor }) {
  const { node, x, y } = anchor;
  return (
    <div
      role="tooltip"
      data-testid="pyramid-ghost-card"
      className="pointer-events-none fixed z-30 w-[220px] rounded-[var(--r-2)] border border-[var(--card-border)] bg-[var(--bg-1)] p-3 shadow-[var(--card-shadow)]"
      style={{ left: x + 12, top: y + 12 }}
    >
      <div className="text-[13px] font-medium text-[var(--fg-1)]">{node.label}</div>
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-[var(--fg-3)]">
        <span>{PILLAR_LABEL[node.pillar]}</span>
        <span className="tabular-nums">weight {node.weight}</span>
      </div>
      <div className="mt-1 font-mono text-[10px] text-[var(--fg-4)] truncate">{node.key}</div>
    </div>
  );
}
