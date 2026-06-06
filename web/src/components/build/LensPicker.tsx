"use client";

// LensPicker — the segmented control that chooses which analysis lens the Build
// Studio reveals (a lens is a math shape: cost × persona, volume × take-rate…).
//
// Honesty gate: options are restricted to the lenses that actually have ≥1
// scenario in this TAM (tam.scenarios.map(s => s.lens)). We never offer an empty
// lens the concept can't size — that would be a dead button promising a method
// that isn't there.
//
// Governance: lens chips use the COOL family (the lens voice), NEVER the tier
// ramp (provenance). A colour means one thing — here it means "which lens is
// live", not "how sourced". The active chip is the single indigo accent.

import { lensLabel } from "@/lib/format";
import type { AnalysisLens, TAMOutput } from "@/lib/schemas";

// The lenses present in a TAM, de-duplicated, in first-seen order (mirrors the
// scenario order the graph reveals). Exported so the view can auto-suggest the
// primary lens without re-deriving the set.
export function lensesInTam(tam: TAMOutput): AnalysisLens[] {
  const seen = new Set<AnalysisLens>();
  const out: AnalysisLens[] = [];
  for (const s of tam.scenarios) {
    if (!seen.has(s.lens)) {
      seen.add(s.lens);
      out.push(s.lens);
    }
  }
  return out;
}

// Auto-suggested lens: the one whose scenarios carry the most method diversity
// (the most frameworks), so the studio opens on the richest available story. Ties
// resolve to first-seen order. Falls back to the first present lens.
export function suggestPrimaryLens(tam: TAMOutput): AnalysisLens | null {
  const lenses = lensesInTam(tam);
  if (lenses.length === 0) return null;
  let best = lenses[0] as AnalysisLens;
  let bestCount = -1;
  for (const lens of lenses) {
    const frameworks = new Set(
      tam.scenarios.filter((s) => s.lens === lens).map((s) => s.framework),
    );
    if (frameworks.size > bestCount) {
      bestCount = frameworks.size;
      best = lens;
    }
  }
  return best;
}

export interface LensPickerProps {
  tam: TAMOutput;
  value: AnalysisLens;
  onChange: (lens: AnalysisLens) => void;
}

export function LensPicker({ tam, value, onChange }: LensPickerProps) {
  const lenses = lensesInTam(tam);
  // A single available lens is not a choice — show it as a static label so we
  // don't render a one-option "picker" that implies an absent alternative.
  if (lenses.length <= 1) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Lens</span>
        <span className="text-[13px] text-[var(--fg-1)]">{value ? lensLabel(value) : "—"}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Analysis lens">
      <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Lens</span>
      <div className="flex flex-wrap gap-1 rounded-[var(--r-2)] bg-[var(--bg-2)] p-1">
        {lenses.map((lens) => {
          const active = lens === value;
          const count = tam.scenarios.filter((s) => s.lens === lens).length;
          return (
            <button
              key={lens}
              type="button"
              // biome-ignore lint/a11y/useSemanticElements: a styled segmented
              // control needs a <button> for the chip layout; role="radio" +
              // aria-checked inside the role="radiogroup" gives the same a11y
              // semantics an <input type="radio"> would, without the input chrome.
              role="radio"
              aria-checked={active}
              onClick={() => onChange(lens)}
              className="flex items-center gap-1.5 rounded-[var(--r-1)] px-3 py-1.5 text-[12px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              style={{
                // Cool family = lens voice (the active lens speaks in the one
                // indigo accent); inactive chips stay neutral. Never tier ramp.
                background: active ? "var(--bg-0)" : "transparent",
                color: active ? "var(--accent-active)" : "var(--fg-3)",
                boxShadow: active ? "inset 0 0 0 1px var(--accent)" : undefined,
              }}
            >
              <span>{lensLabel(lens)}</span>
              <span className="tabular-nums text-[var(--fg-4)]">{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
