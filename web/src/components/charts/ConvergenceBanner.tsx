"use client";

// Convergence banner (MV2 · tournament champion). The cross-check a VC otherwise
// assembles by hand: size the same market top-down AND bottoms-up, then see how
// far the two independent methods disagree. Strata already has both sourced
// scenarios — this surfaces "bottoms-up $X · top-down $Y · agree N×" as the
// headline trust signal. Pure synthesis of sourced values; renders ONLY when the
// backend supplies a `convergence` object (≥2 independent method families), never
// manufacturing a second method. All motion is reduced-motion-gated via CountUp.

import { useEffect, useState } from "react";

import { CountUp, FadeIn } from "@/components/ui/motion";
import { familyLabel, formatCompact } from "@/lib/format";
import type { Convergence } from "@/lib/schemas";

// Agreement grading — honest framing, never "confidence". Tight methods (≤1.5×)
// read as corroboration; a wide spread is flagged, not hidden.
function grade(ratio: number): { label: string; token: string } {
  if (ratio <= 1.5) return { label: "tight agreement", token: "var(--success)" };
  if (ratio <= 2.5) return { label: "broad agreement", token: "var(--accent)" };
  return { label: "wide spread", token: "var(--warning)" };
}

export function ConvergenceBanner({ convergence }: { convergence: Convergence }) {
  const { low_family, high_family, low_value, high_value, ratio, unit } = convergence;
  const { label, token } = grade(ratio);

  // The spread bar grows from collapsed → full on mount, so the eye reads the
  // two methods sliding apart to their true distance. Skipped under reduced motion.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setGrown(true);
      return;
    }
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <FadeIn>
      <div className="canvas-card overflow-hidden p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
            Method agreement
          </div>
          <div
            className="rounded-[var(--r-round)] px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wide"
            style={{
              color: token,
              background: "color-mix(in srgb, currentColor 14%, transparent)",
            }}
          >
            {label}
          </div>
        </div>

        {/* Headline: the agreement multiple, counted up. The figure is the trust
            signal, so it leads at display scale — and in mono (Numbers-Are-Mono),
            never the serif: a ratio is data, not an editorial headline. */}
        <div className="mt-3 flex items-baseline gap-2.5">
          <span className="tam-num text-[52px] leading-none text-[var(--fg-1)]">
            <CountUp value={ratio} format={(n) => `${n.toFixed(1)}×`} durationMs={750} />
          </span>
          <span className="text-[13px] leading-snug text-[var(--fg-3)]">
            spread between two independent methods
          </span>
        </div>

        {/* Convergence bar: two method markers at their true relative distance. */}
        <div className="mt-5">
          <div className="relative h-2 rounded-full bg-[var(--bg-3)]">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
              style={{
                width: grown ? "100%" : "0%",
                background: `linear-gradient(90deg, var(--accent), ${token})`,
              }}
            />
            <Marker side="left" />
            <Marker side="right" token={token} />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4">
            {/* Role is the positional fact (lower vs higher estimate), always
                true by construction; the actual method is named beneath it, so a
                non-standard family pair is never mislabelled "bottoms-up". */}
            <MethodPill
              position="Lower estimate"
              family={familyLabel(low_family)}
              value={low_value}
              unitFmt={(n) => formatCompact(n, unit)}
              align="left"
              token="var(--accent)"
            />
            <MethodPill
              position="Higher estimate"
              family={familyLabel(high_family)}
              value={high_value}
              unitFmt={(n) => formatCompact(n, unit)}
              align="right"
              token={token}
            />
          </div>
        </div>

        <p className="mt-4 text-[12px] leading-relaxed text-[var(--fg-3)]">
          The triangulation a VC assembles by hand: the same market sized two ways from independent
          sources. Closer to 1× means the methods corroborate — this is agreement between sourced
          numbers, not a confidence score.
        </p>
      </div>
    </FadeIn>
  );
}

function Marker({ side, token }: { side: "left" | "right"; token?: string }) {
  return (
    <div
      className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full border-2 border-[var(--bg-1)]"
      style={{
        [side]: 0,
        background: token ?? "var(--accent)",
        boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
      }}
    />
  );
}

function MethodPill({
  position,
  family,
  value,
  unitFmt,
  align,
  token,
}: {
  position: string;
  family: string;
  value: number;
  unitFmt: (n: number) => string;
  align: "left" | "right";
  token: string;
}) {
  return (
    <div className={align === "right" ? "text-right" : "text-left"}>
      <div
        className="flex items-center gap-1.5"
        style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}
      >
        <span className="h-2 w-2 rounded-full" style={{ background: token }} />
        <span className="font-mono text-[10px] uppercase tracking-wide text-[var(--fg-3)]">
          {position}
        </span>
      </div>
      <div className="tam-num mt-1 text-[22px] text-[var(--fg-1)]">
        <CountUp value={value} format={unitFmt} durationMs={750} />
      </div>
      <div className="text-[11px] text-[var(--fg-3)]">{family}</div>
    </div>
  );
}
