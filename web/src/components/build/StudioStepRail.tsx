"use client";

// StudioStepRail — the running ledger beside the Build Studio graph. As the
// reveal cursor advances, each step lands here as a row: its label, the running
// market size (tabular mono), and — for role leaves — the SourceTag (tier dot from
// the tier ramp, source link, snapshot pin). This is the textual twin of the
// staged graph, and the surface AT users read (the aria-live headline lives in the
// view; this rail is the persistent record).
//
// "Reveal all" is the explicit skip-the-show control (and the keyboard path): one
// click jumps the cursor to the last step. Save/Share are pinned at the bottom
// like the workhorse Export section — Share copies the /tam/<hash> address; Save
// is the PR1 workspace hand-off (the steered tree already round-trips via ?s=).

import { SourceTag } from "@/components/build/BuildStudioGraph";
import { AccordionSection } from "@/components/rail/AccordionSection";
import { Button } from "@/components/ui/Button";
import { StaggerItem } from "@/components/ui/motion";
import type { BuildStep } from "@/lib/build-studio";
import { formatCompact } from "@/lib/format";

export interface StudioStepRailProps {
  steps: BuildStep[];
  // How many steps are revealed (cursor). Rows [0, cursor) render.
  cursor: number;
  // True once every step is revealed — hides the "Reveal all" affordance.
  complete: boolean;
  // Jump the cursor to the end (skip the staged reveal).
  onRevealAll: () => void;
  // Copy the current /build|/tam URL (the steered tree's shareable address).
  onShare: () => void;
  // True for the brief "copied" confirmation on Share.
  shared?: boolean;
}

export function StudioStepRail({
  steps,
  cursor,
  complete,
  onRevealAll,
  onShare,
  shared = false,
}: StudioStepRailProps) {
  const revealed = steps.slice(0, cursor);

  return (
    <aside className="flex w-full flex-col gap-3 lg:w-[var(--right-rail-w)] lg:shrink-0">
      <AccordionSection title="Building" badge={`${cursor}/${steps.length}`} pinned>
        {!complete ? (
          <div className="mb-2">
            <Button variant="ghost" sm onClick={onRevealAll} className="justify-start">
              Reveal all →
            </Button>
          </div>
        ) : null}

        {revealed.length === 0 ? (
          <p className="text-[13px] text-[var(--fg-3)]">Sizing…</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {revealed.map((step) => (
              <StaggerItem key={step.id}>
                <li
                  className="canvas-card flex flex-col gap-1.5 px-3 py-2.5"
                  style={{ borderRadius: "var(--r-2)" }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="min-w-0 truncate text-[13px] capitalize text-[var(--fg-1)]">
                      {step.label}
                    </span>
                    <span className="tam-num shrink-0 text-[13px] tabular-nums text-[var(--fg-1)]">
                      {formatCompact(step.runningValue, step.unit)}
                    </span>
                  </div>
                  {step.kind === "role" ? (
                    <SourceTag
                      sourceUrl={step.sourceUrl}
                      tier={step.tier}
                      snapshot={step.snapshot}
                    />
                  ) : null}
                </li>
              </StaggerItem>
            ))}
          </ul>
        )}
      </AccordionSection>

      <AccordionSection title="Share" pinned>
        <div className="flex flex-col gap-2">
          <Button variant="ghost" sm onClick={onShare} className="justify-start">
            {shared ? "Copied!" : "Copy link"}
          </Button>
          <p className="text-[11px] leading-[1.4] text-[var(--fg-3)]">
            The steered tree rides the URL — sharing this link reproduces exactly what you see.
          </p>
        </div>
      </AccordionSection>
    </aside>
  );
}
