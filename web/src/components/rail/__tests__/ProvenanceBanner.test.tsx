/** Phase 4 — the loud "MODELED — NOT SOURCED" provenance treatment. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TAMOutput } from "@/lib/schemas";
import { ProvenanceBanner, modeledInputNotes } from "../ProvenanceBanner";

// Minimal TAMOutput shape — the banner reads only scenarios[].banners + the two
// rolled-up flags, so we cast a focused fixture rather than a full artifact.
function tam(partial: {
  banners?: { kind: string; message: string }[][];
  synthetic?: boolean;
  modeledComposite?: boolean;
}): TAMOutput {
  return {
    scenarios: (partial.banners ?? []).map((banners) => ({ banners })),
    uses_synthetic_primitives: partial.synthetic ?? false,
    uses_modeled_composites: partial.modeledComposite ?? false,
  } as unknown as TAMOutput;
}

const MODELED_MSG = "AI coding-assistant ACV is MODELED, not a sourced measurement. Do not cite.";

describe("ProvenanceBanner", () => {
  it("renders nothing when there are no banners or flags", () => {
    const { container } = render(<ProvenanceBanner tam={tam({})} />);
    expect(container.firstChild).toBeNull();
  });

  it("surfaces a loud MODELED label and the per-input message", () => {
    render(
      <ProvenanceBanner tam={tam({ banners: [[{ kind: "modeled", message: MODELED_MSG }]] })} />,
    );
    // The literal word carries the meaning textually (not colour alone) — WCAG AA.
    expect(screen.getByText(/modeled — not sourced/i)).toBeTruthy();
    expect(screen.getByText(MODELED_MSG)).toBeTruthy();
  });

  it("is an accessible, non-dismissable note (announced via role=note, no dismiss control)", () => {
    render(
      <ProvenanceBanner tam={tam({ banners: [[{ kind: "modeled", message: MODELED_MSG }]] })} />,
    );
    expect(screen.getByRole("note")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("dedupes the same modeled message across scenarios", () => {
    render(
      <ProvenanceBanner
        tam={tam({
          banners: [
            [{ kind: "modeled", message: MODELED_MSG }],
            [{ kind: "modeled", message: MODELED_MSG }],
          ],
        })}
      />,
    );
    expect(screen.getAllByText(MODELED_MSG)).toHaveLength(1);
  });

  it("covers the analyst-paraphrase + dark-estimate tiers (wire kind values, hyphenated)", () => {
    const para = "Paraphrased from Gartner; verify against the full text.";
    const dark = "Dark estimate — modeled from indirect signals.";
    expect(
      modeledInputNotes(tam({ banners: [[{ kind: "analyst-paraphrase", message: para }]] })),
    ).toEqual([para]);
    expect(
      modeledInputNotes(tam({ banners: [[{ kind: "dark-estimate", message: dark }]] })),
    ).toEqual([dark]);
  });

  it("still shows the rolled-up synthetic/composite notes", () => {
    render(<ProvenanceBanner tam={tam({ synthetic: true })} />);
    expect(screen.getByText(/synthetic primitive/i)).toBeTruthy();
  });

  it("ignores a sourced scenario with no estimate banners", () => {
    const notes = modeledInputNotes(
      tam({ banners: [[{ kind: "private", message: "tenant data" }]] }),
    );
    expect(notes).toEqual([]);
  });
});
