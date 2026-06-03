// Always name BOTH canonical sizing directions (sub-project 2 honesty rule):
// a TAM should never present one direction as the answer without saying which
// direction is missing. Derived purely from method_families_used — when a
// direction is absent we SAY so; we never fabricate a second method.

import type { MethodFamily } from "@/lib/schemas";

// The two canonical directions; the remaining families are additional
// triangulation approaches, not substitutes for the missing direction.
const TOP_DOWN: MethodFamily = "top_down_spend";
const BOTTOMS_UP: MethodFamily = "bottoms_up_seats";

const EXTRA_LABEL: Partial<Record<MethodFamily, string>> = {
  comparable_revenue: "comparable revenue",
  analog_penetration: "analog penetration",
  value_chain: "value chain",
};

export function MethodDirections({ families }: { families: MethodFamily[] }) {
  const fams = new Set(families);
  const hasTop = fams.has(TOP_DOWN);
  const hasBottom = fams.has(BOTTOMS_UP);
  const extras = families.filter((f) => EXTRA_LABEL[f]).map((f) => EXTRA_LABEL[f]);

  return (
    <div
      data-testid="method-directions"
      className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px]"
    >
      <Direction label="Top-down" present={hasTop} />
      <span className="text-[var(--fg-4)]">∧</span>
      <Direction label="Bottoms-up" present={hasBottom} />
      {extras.length > 0 ? (
        <span className="text-[var(--fg-3)]">+ {extras.join(" · ")}</span>
      ) : null}
      {!hasTop || !hasBottom ? (
        <span className="text-[var(--fg-3)]">
          — no {!hasTop && !hasBottom ? "top-down or bottoms-up" : !hasTop ? "top-down" : "bottoms-up"}{" "}
          method in the data bank yet
          {/* A TAM backed by ≥2 non-canonical families IS cross-checked — say
              that, rather than mislabel it "single-direction". */}
          {families.length >= 2
            ? "; independently cross-checked by the methods above instead."
            : ", so this estimate is single-direction."}
        </span>
      ) : null}
    </div>
  );
}

function Direction({ label, present }: { label: string; present: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1"
      style={{ color: present ? "var(--fg-1)" : "var(--fg-4)" }}
    >
      <span
        aria-hidden="true"
        className="size-1.5 rounded-full"
        style={{ background: present ? "var(--tier-regulator)" : "var(--fg-4)" }}
      />
      {label}
      <span className="text-[11px]">{present ? "✓" : "✗"}</span>
    </span>
  );
}
