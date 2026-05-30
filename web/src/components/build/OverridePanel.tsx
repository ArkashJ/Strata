"use client";

// The edit→recompute entry point. Opens when a base-value primitive node on the
// /build graph is clicked. Two ways to change an assumption:
//
//   • What-if  — type/slide a transient scalar. NEVER persisted as a primitive
//                (Q20): it rides in the URL only and the backend flags every
//                scenario it touches with a `user_override` banner. This is the
//                "what if WTP were $X" calculator.
//   • Swap     — re-point this input to a DIFFERENT already-sourced primitive
//                from the same concept (schema-pure; no banner). The backend
//                validates the swapped primitive's unit against the framework's
//                input signature and 422s on a mismatch.
//
// Applying either re-mints the /build URL; BuildHashView then POSTs the overrides
// to /build/recompute and the headline + graph + charts recompute.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { formatCompact } from "@/lib/format";
import { primitivesQuery } from "@/lib/queries";
import type { InputUsed, Unit } from "@/lib/schemas";

export interface OverridePanelProps {
  input: InputUsed;
  frameworkSlug: string;
  conceptSlug: string;
  // Active what-if value for this primitive, if one is set.
  currentOverride?: number;
  // Active swap target slug for this input, if one is set.
  currentSwap?: string;
  onApplyWhatIf: (value: number, unit: Unit) => void;
  onApplySwap: (primitiveSlug: string) => void;
  onClear: () => void;
  onClose: () => void;
}

type Tab = "whatif" | "swap";

export function OverridePanel({
  input,
  frameworkSlug,
  conceptSlug,
  currentOverride,
  currentSwap,
  onApplyWhatIf,
  onApplySwap,
  onClear,
  onClose,
}: OverridePanelProps) {
  const baseline = input.value ?? null;
  const unit = input.unit ?? null;
  const hasActive = currentOverride !== undefined || currentSwap !== undefined;
  const [tab, setTab] = useState<Tab>("whatif");

  const label = input.name ?? input.primitive_slug.replace(/-/g, " ");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={`Edit assumption: ${label}`}
    >
      <div
        className="canvas-card w-full max-w-[440px] p-6"
        style={{ borderRadius: "var(--r-4)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
              {input.role.replace(/_/g, " ")} · {frameworkSlug.replace(/-/g, " ")}
            </div>
            <h2 className="display mt-1 truncate text-[20px] text-[var(--fg-1)]">{label}</h2>
            {baseline != null && unit ? (
              <div className="mt-1 text-[13px] text-[var(--fg-3)]">
                sourced baseline:{" "}
                <span className="tam-num text-[var(--fg-1)]">{formatCompact(baseline, unit)}</span>
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[18px] leading-none text-[var(--fg-3)] hover:text-[var(--fg-1)]"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="mt-4 flex gap-1 rounded-[var(--r-2)] bg-[var(--bg-2)] p-1 text-[12px]">
          <TabButton active={tab === "whatif"} onClick={() => setTab("whatif")}>
            What-if value
          </TabButton>
          <TabButton active={tab === "swap"} onClick={() => setTab("swap")}>
            Swap primitive
          </TabButton>
        </div>

        <div className="mt-4">
          {tab === "whatif" ? (
            <WhatIfTab
              baseline={baseline}
              unit={unit}
              current={currentOverride}
              onApply={(v) => unit && onApplyWhatIf(v, unit)}
            />
          ) : (
            <SwapTab
              conceptSlug={conceptSlug}
              currentSlug={input.primitive_slug}
              currentSwap={currentSwap}
              onApply={onApplySwap}
            />
          )}
        </div>

        {hasActive ? (
          <div className="mt-4 flex items-center justify-between border-t border-[var(--border-1)] pt-3">
            <span className="text-[12px] text-[var(--accent)]">an override is active on this input</span>
            <Button variant="ghost" sm onClick={onClear}>
              Reset to sourced
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex-1 rounded-[var(--r-1)] px-3 py-1.5 transition-colors"
      style={{
        background: active ? "var(--bg-0)" : "transparent",
        color: active ? "var(--fg-1)" : "var(--fg-3)",
      }}
    >
      {children}
    </button>
  );
}

function WhatIfTab({
  baseline,
  unit,
  current,
  onApply,
}: {
  baseline: number | null;
  unit: Unit | null;
  current?: number;
  onApply: (value: number) => void;
}) {
  const start = current ?? baseline ?? 0;
  const [value, setValue] = useState<number>(start);

  if (baseline == null || !unit) {
    // No numeric baseline/unit to anchor a what-if — refuse rather than invent a
    // scale. Swapping to a sourced primitive is the honest path here.
    return (
      <p className="text-[13px] leading-[1.5] text-[var(--fg-3)]">
        This input has no enriched numeric value to anchor a what-if. Use{" "}
        <span className="text-[var(--fg-1)]">Swap primitive</span> to re-point it to a sourced figure.
      </p>
    );
  }

  // Slider spans 0–3× the sourced baseline: enough to explore upside/downside
  // without implying any value is sourced. The number input is unbounded.
  const sliderMax = Math.max(baseline * 3, value * 1.2, 1);
  const delta = baseline !== 0 ? (value - baseline) / baseline : 0;
  // Float-safe "unchanged" check — strict === would mis-fire after a slider
  // round-trip or when baseline is 0.
  const unchanged = Math.abs(value - baseline) < Math.abs(baseline) * 1e-9;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <span className="tam-num text-[28px] text-[var(--fg-1)]">{formatCompact(value, unit)}</span>
        {Number.isFinite(delta) && delta !== 0 ? (
          <span
            className="text-[13px]"
            style={{ color: delta > 0 ? "var(--pos, var(--accent))" : "var(--fg-3)" }}
          >
            {delta > 0 ? "+" : ""}
            {(delta * 100).toFixed(0)}% vs sourced
          </span>
        ) : null}
      </div>

      <input
        type="range"
        min={0}
        max={sliderMax}
        step={sliderMax / 100}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className="w-full accent-[var(--accent)]"
        aria-label="What-if value"
      />

      <input
        type="number"
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className="w-full rounded-[var(--r-2)] border border-[var(--border-1)] bg-[var(--bg-0)] px-3 py-2 text-[14px] text-[var(--fg-1)]"
      />

      <p className="text-[11px] leading-[1.4] text-[var(--fg-3)]">
        What-if values are not sourced. Scenarios they touch are flagged with a “user override” banner
        and footnoted in exports.
      </p>

      <Button variant="primary" sm onClick={() => onApply(value)} disabled={unchanged}>
        Recompute with {formatCompact(value, unit)}
      </Button>
    </div>
  );
}

function SwapTab({
  conceptSlug,
  currentSlug,
  currentSwap,
  onApply,
}: {
  conceptSlug: string;
  currentSlug: string;
  currentSwap?: string;
  onApply: (primitiveSlug: string) => void;
}) {
  const primitives = useQuery(primitivesQuery);

  // Candidate swaps: other sourced primitives in the SAME concept that carry a
  // numeric value. The backend validates the unit signature and 422s on a real
  // mismatch, so we keep the client filter permissive (same concept) rather than
  // trying to compare structured units against the summary's unit_label string.
  const candidates = (primitives.data ?? []).filter(
    (p) => p.concept_slug === conceptSlug && p.value != null && p.slug !== currentSlug,
  );

  if (primitives.isPending) {
    return <p className="text-[13px] text-[var(--fg-3)]">Loading primitives…</p>;
  }
  if (candidates.length === 0) {
    return (
      <p className="text-[13px] leading-[1.5] text-[var(--fg-3)]">
        No other sourced primitives in this concept to swap in. Use a what-if value instead.
      </p>
    );
  }

  return (
    <ul className="flex max-h-[280px] flex-col gap-1.5 overflow-auto">
      {candidates.map((p) => {
        const active = currentSwap === p.slug;
        return (
          <li key={p.slug}>
            <button
              type="button"
              onClick={() => onApply(p.slug)}
              className="canvas-card flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
              style={{
                borderRadius: "var(--r-2)",
                outline: active ? "2px solid var(--accent)" : undefined,
              }}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] text-[var(--fg-1)]">{p.name}</span>
                <span className="text-[11px] text-[var(--fg-3)]">{p.unit_label}</span>
              </span>
              <span className="tam-num shrink-0 text-[13px] tabular-nums text-[var(--fg-1)]">
                {p.value != null ? p.value.toLocaleString() : "—"}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
