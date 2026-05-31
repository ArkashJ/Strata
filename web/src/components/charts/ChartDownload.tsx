"use client";

// Small PNG / SVG download control for any chart section. Point it at the
// container that wraps a recharts chart; on click it grabs the first <svg> in
// that subtree and exports it client-side (see lib/chart-export). Used to make
// every result/sensitivity/trajectory graph forwardable into a memo or deck.

import { type RefObject, useState } from "react";

import { downloadChartPng, downloadChartSvg, resolveCssVar } from "@/lib/chart-export";

export function ChartDownload({
  containerRef,
  filename,
  className,
}: {
  containerRef: RefObject<HTMLElement | null>;
  filename: string;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);

  function svg(): SVGSVGElement | null {
    return containerRef.current?.querySelector("svg") ?? null;
  }

  async function onPng() {
    const el = svg();
    if (!el || busy) return;
    setBusy(true);
    try {
      await downloadChartPng(el, filename, resolveCssVar("--bg-1", "#ffffff"));
    } finally {
      setBusy(false);
    }
  }

  function onSvg() {
    const el = svg();
    if (el) downloadChartSvg(el, filename);
  }

  return (
    <div className={`flex items-center gap-1.5 ${className ?? ""}`} data-export-hide>
      <button
        type="button"
        onClick={onPng}
        disabled={busy}
        className="rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)] disabled:opacity-50"
        title="Download chart as PNG"
      >
        PNG
      </button>
      <button
        type="button"
        onClick={onSvg}
        className="rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)]"
        title="Download chart as SVG"
      >
        SVG
      </button>
    </div>
  );
}
