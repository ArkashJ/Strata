"use client";

// ReportHeadline — the Coatue/Gartner editorial frame around a single chart or
// section: a BOLD editorial headline (the takeaway, not a label), a muted
// subtitle naming the metric + unit, the chart body, then a pinned source
// footnote. This is the recurring "slide" unit of a $1M deck: the eye reads the
// claim first, the evidence second, the provenance third.
//
// It is APP-SCOPED on purpose (depends on app tokens --fg-*/--border-*) — the
// look IS the token system. Honesty-fenced: pass `source={null}` and the
// footnote renders nothing rather than fabricating "source: …".

import type * as React from "react";

interface ReportHeadlineProps {
  // The takeaway, stated as a sentence (Coatue: "AI is still early in its
  // journey but massive adoption so far!"). Rendered in the Instrument Serif
  // display face — this is the one place a chart wears the editorial voice.
  headline: string;
  // The metric + unit beneath, in muted sans (Coatue: "US % penetration").
  subtitle?: string;
  // Pinned source footnote. null/undefined → nothing rendered (no fabrication).
  source?: string | null;
  // Optional eyebrow above the headline (section number / kicker).
  eyebrow?: string;
  className?: string;
  children: React.ReactNode;
}

export function ReportHeadline({
  headline,
  subtitle,
  source,
  eyebrow,
  className,
  children,
}: ReportHeadlineProps) {
  return (
    <figure className={className}>
      {eyebrow ? (
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--fg-3)]">
          {eyebrow}
        </div>
      ) : null}
      <figcaption className="mt-1">
        <h3 className="display text-[clamp(22px,2.6vw,32px)] leading-[1.12] text-[var(--fg-1)]">
          {headline}
        </h3>
        {subtitle ? <p className="mt-1.5 text-[13px] text-[var(--fg-3)]">{subtitle}</p> : null}
      </figcaption>

      <div className="mt-4 border-t border-[var(--border-1)] pt-4">{children}</div>

      {source ? (
        <div className="mt-3 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] leading-relaxed text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}
