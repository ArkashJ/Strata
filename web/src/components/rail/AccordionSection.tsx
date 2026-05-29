"use client";

// One collapsible section of the build/tam right rail (U2). Extracted from the
// per-view `RailSection` locals so /build and /tam render an identical rail.
//
// Open/close is *not* a meaningful state change (U6) — it never mints a URL, so
// it stays in local component state here and the parent passes only the initial
// `defaultOpen`. `pinned` sections (Target, Export) render without a toggle so
// they read as always-visible anchors at the top/bottom of the accordion.
import { useState } from "react";

export interface AccordionSectionProps {
  title: string;
  // One-line summary chip on the right (e.g. independence score, count).
  badge?: string;
  defaultOpen?: boolean;
  // Pinned sections (Target, Export) have no collapse affordance — always shown.
  pinned?: boolean;
  children: React.ReactNode;
}

export function AccordionSection({
  title,
  badge,
  defaultOpen = false,
  pinned = false,
  children,
}: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const expanded = pinned || open;

  return (
    <section
      data-rail-section={title}
      className="canvas-card"
      style={{ borderRadius: "var(--r-3)" }}
    >
      {pinned ? (
        <div className="flex items-center justify-between px-4 pt-3">
          <h3 className="text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--fg-3)]">
            {title}
          </h3>
          {badge ? (
            <span className="text-[12px] tabular-nums text-[var(--fg-2)]">{badge}</span>
          ) : null}
        </div>
      ) : (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between px-4 py-3 text-left"
        >
          <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--fg-3)]">
            <span className="text-[var(--fg-4)]">{open ? "▾" : "▸"}</span>
            {title}
          </span>
          {badge ? (
            <span className="text-[12px] tabular-nums text-[var(--fg-2)]">{badge}</span>
          ) : null}
        </button>
      )}
      {expanded ? <div className="px-4 pb-3 pt-1">{children}</div> : null}
    </section>
  );
}
