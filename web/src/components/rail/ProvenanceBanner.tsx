// Provenance banner (U2 "Banners" section · data-layer Q20/Q33/Q36/Q37). Pure
// commentary surfaced from data-layer decisions — synthetic-atomic, modeled-
// composite, etc. — never affecting the math (E1). Non-dismissable: a TAM that
// leans on a modeled assumption must say so wherever it renders, so /build and
// /tam share this one component.
//
// The full per-input source-tier mix the capture wants ("N of M inputs are
// community-tier") isn't carried on inputs_used yet — see the TODO in
// TamDetailView. We surface only the flags the API does expose.
import type { TAMOutput } from "@/lib/schemas";

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

export function ProvenanceBanner({ tam }: { tam: TAMOutput }) {
  const notes = provenanceNotes(tam);
  if (notes.length === 0) return null;

  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-[var(--r-3)] px-4 py-3 text-[13px] text-[var(--fg-2)]"
      style={{
        background: "var(--tier-analyst-tint)",
        border: "1px solid color-mix(in srgb, var(--warning) 30%, transparent)",
      }}
    >
      <span className="mt-0.5 font-medium text-[var(--warning)]">Provenance</span>
      <span>This TAM {notes.join(" It also ")}</span>
    </div>
  );
}
