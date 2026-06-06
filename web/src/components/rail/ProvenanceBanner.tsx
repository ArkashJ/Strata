// Provenance banner (U2 "Banners" section · data-layer Q20/Q33/Q36/Q37). Pure
// commentary surfaced from data-layer decisions — synthetic-atomic, modeled-
// composite, per-input MODELED estimates — never affecting the math (E1).
// Non-dismissable: a TAM that leans on a modeled assumption must say so wherever
// it renders, so /build and /tam share this one component.
//
// Phase 4 (soft-data fence) makes the loud "MODELED — NOT SOURCED" treatment the
// consuming surface for the per-scenario MODELED ScenarioBanners the evaluator
// now emits for every estimate (incl. the formerly-silent analyst tier). The
// literal words "MODELED — NOT SOURCED" carry the meaning textually, never by
// colour alone (WCAG 2.2 AA); the note is keyboard-reachable and non-dismissable.
import type { TAMOutput } from "@/lib/schemas";

// Banner kinds that mark a NON-SOURCED estimate (vs a sourced measurement). The
// backend emits these per-scenario on inputs_used that are modeled/paraphrased/
// synthesized; we surface them by their own message so each named input is loud.
const MODELED_BANNER_KINDS = new Set([
  "modeled",
  "analyst-paraphrase",
  "synthetic",
  "dark-estimate",
]);

// Distinct per-input MODELED notes across every scenario (deduped by message),
// e.g. "AI coding-assistant ACV is MODELED, not a sourced measurement…".
export function modeledInputNotes(tam: TAMOutput): string[] {
  const seen = new Set<string>();
  for (const scenario of tam.scenarios) {
    for (const banner of scenario.banners) {
      if (MODELED_BANNER_KINDS.has(banner.kind)) seen.add(banner.message);
    }
  }
  return [...seen];
}

// The rolled-up TAM-level flags (synthetic atomic / modeled composite).
export function provenanceNotes(tam: TAMOutput): string[] {
  const notes: string[] = [];
  if (tam.uses_synthetic_primitives) {
    notes.push("uses a synthetic primitive (range-bounded, expiry-gated) — review before citing.");
  }
  if (tam.uses_modeled_composites) {
    notes.push(
      "uses a community-modeled composite — the result depends on the modeling assumption.",
    );
  }
  return notes;
}

export function ProvenanceBanner({ tam, className = "" }: { tam: TAMOutput; className?: string }) {
  const modeled = modeledInputNotes(tam);
  const notes = provenanceNotes(tam);
  if (modeled.length === 0 && notes.length === 0) return null;

  return (
    <div
      role="note"
      aria-label="Provenance — modeled inputs"
      className={`flex flex-col gap-2 rounded-[var(--r-3)] px-4 py-3 text-[13px] text-[var(--fg-1)] ${className}`}
      style={{
        background: "var(--tier-analyst-tint)",
        borderLeft: "4px solid var(--warning)",
        border: "1px solid color-mix(in srgb, var(--warning) 45%, transparent)",
        borderLeftWidth: "4px",
      }}
    >
      {modeled.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="font-semibold uppercase tracking-wide text-[var(--warning)]">
            Modeled — not sourced
          </span>
          <ul className="ml-4 list-disc text-[var(--fg-2)]">
            {modeled.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </div>
      )}
      {notes.length > 0 && (
        <div className="flex items-start gap-2">
          <span className="mt-0.5 font-medium text-[var(--warning)]">Provenance</span>
          <span className="text-[var(--fg-2)]">This TAM {notes.join(" It also ")}</span>
        </div>
      )}
    </div>
  );
}
