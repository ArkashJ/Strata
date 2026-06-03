"use client";

// Sub-project 1 — the visible payoff of the scope guard. ScopeStrip shows the
// declared market as chips; ScopeWarnings explains, per consumed primitive, when
// the source behind a number is narrower/broader than that declared market — the
// reason two methods can disagree. The displayed scope is always the primitive's
// own truth (snap-to-truth); these are read-only on the frozen /tam artifact.

import { codedTagLabel } from "@/lib/format";
import type { MarketScope, ScopeReport } from "@/lib/schemas";

// A relationship's tone: a definite size mismatch is a warning; a wrong-market
// (disjoint) is an error. Anything else falls back to neutral.
const REL_TONE: Record<string, string> = {
  narrower: "var(--warning)",
  broader: "var(--warning)",
  partial: "var(--warning)",
  disjoint: "var(--danger)",
};

type Chip = { key: string; label: string };

function scopeChips(scope: MarketScope): Chip[] {
  const chips: Chip[] = [];
  for (const t of scope.vertical) {
    chips.push({ key: `v-${t.code}`, label: codedTagLabel(t) });
  }
  for (const t of scope.persona) {
    chips.push({ key: `p-${t.code}`, label: codedTagLabel(t) });
  }
  if (scope.segment) chips.push({ key: "seg", label: scope.segment.label });
  for (const g of scope.geo_demand) chips.push({ key: `gd-${g}`, label: g });
  // Supply geo only when it differs from demand — usually identical.
  for (const g of scope.geo_supply) {
    if (!scope.geo_demand.includes(g)) chips.push({ key: `gs-${g}`, label: g });
  }
  for (const p of scope.product) chips.push({ key: `prod-${p}`, label: p });
  return chips;
}

export function ScopeStrip({ scope }: { scope: MarketScope }) {
  const chips = scopeChips(scope);
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="scope-strip">
      <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Market</span>
      {chips.map((c) => (
        <span
          key={c.key}
          className="inline-flex items-center rounded-[var(--r-round)] bg-[var(--bg-2)] px-2.5 py-1 text-[11px] text-[var(--fg-1)]"
        >
          {c.label}
        </span>
      ))}
    </div>
  );
}

export function ScopeWarnings({ report }: { report: ScopeReport }) {
  const flagged = report.inputs.filter((i) => i.warnings.length > 0);
  return (
    <div data-testid="scope-check">
      <h2 className="display text-[24px] text-[var(--fg-1)]">Scope check</h2>
      <p className="mt-1 text-[13px] text-[var(--fg-3)]">
        {report.ok
          ? "Every number's source matches the declared market."
          : `${flagged.length} input${flagged.length === 1 ? "" : "s"} cover a narrower or broader market than declared — why the methods can disagree. Each tag shows the source's true scope.`}
      </p>
      {flagged.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2">
          {flagged.map((inp) => (
            <li key={inp.primitive_slug} className="canvas-card flex flex-col gap-1.5 p-3">
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="font-medium text-[var(--fg-1)]">{inp.role_name}</span>
                <span className="text-[var(--fg-4)]">·</span>
                <span className="font-mono text-[var(--fg-3)]">{inp.primitive_slug}</span>
              </div>
              {inp.warnings.map((w) => (
                <div
                  key={`${inp.primitive_slug}-${w.dimension}`}
                  className="flex items-start gap-2 text-[13px] text-[var(--fg-2)]"
                >
                  <span
                    aria-hidden="true"
                    className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: REL_TONE[w.relationship] ?? "var(--fg-4)" }}
                  />
                  <span>
                    <span
                      className="mr-1 text-[11px] font-medium uppercase tracking-wide"
                      style={{ color: REL_TONE[w.relationship] ?? "var(--fg-3)" }}
                    >
                      {w.relationship}
                    </span>
                    {w.message}
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// Compact at-a-glance summary for the right rail.
export function ScopeRailSummary({ report }: { report: ScopeReport }) {
  const flagged = report.inputs.filter((i) => i.warnings.length > 0).length;
  return (
    <div className="flex items-center gap-2 text-[13px]">
      <span
        aria-hidden="true"
        className="size-2 shrink-0 rounded-full"
        style={{ background: report.ok ? "var(--tier-regulator)" : "var(--warning)" }}
      />
      <span className="text-[var(--fg-2)]">
        {report.ok
          ? "All inputs match the declared market"
          : `${flagged} input${flagged === 1 ? "" : "s"} off-scope`}
      </span>
    </div>
  );
}
