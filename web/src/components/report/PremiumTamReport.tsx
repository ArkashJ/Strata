"use client";

// PremiumTamReport — the page-level wrapper that renders the PremiumReport from
// a real /tam/<hash> artifact: it fetches the TAM's sensitivity (the only extra
// the core API exposes today) and feeds it into the composer. Competitive +
// adoption payloads are not sourced yet, so those sections degrade to honest
// gaps inside PremiumReport (Q20 — no fabricated shares or CAGRs).
//
// Layout + print stylesheet mirror the classic TamReport so "Save as PDF" stays
// clean; the difference is the editorial Coatue/Gartner section system.

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/Button";
import { sensitivityQuery } from "@/lib/queries";
import type { TAMOutput } from "@/lib/schemas";
import { PremiumReport } from "./PremiumReport";

export function PremiumTamReport({ tam }: { tam: TAMOutput }) {
  // Sensitivity is keyed on the registry concept slug; the same query the
  // classic report and the /tam tornado use. Failure → the section shows its
  // honest gap, never a fabricated tornado.
  const sensitivity = useQuery(sensitivityQuery(tam.target.concept));

  // Honor the shared ?print=1 convention (other surfaces open the report this
  // way to auto-trigger Save-as-PDF), one-shot after first paint.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!new URLSearchParams(window.location.search).has("print")) return;
    const t = window.setTimeout(() => window.print(), 600);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <main className="tam-report mx-auto w-full max-w-[900px] px-6 py-10 sm:px-8">
      <ReportPrintStyles />

      <div data-print-hide className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/tam/${tam.state_hash}`}
          className="text-[13px] text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)]"
        >
          ← Back to interactive TAM
        </Link>
        <Button sm onClick={() => window.print()}>
          Print / Save as PDF
        </Button>
      </div>

      <header className="mb-8 border-b-2 border-[var(--fg-1)] pb-4">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--fg-3)]">
            Strata · Market Sizing Report
          </span>
          <span className="font-mono text-[11px] text-[var(--fg-3)]">
            {tam.created_at.slice(0, 10)}
          </span>
        </div>
      </header>

      <PremiumReport tam={tam} payload={{ sensitivity: sensitivity.data ?? null }} />
    </main>
  );
}

// Print stylesheet — drops interactive chrome, keeps each section together.
function ReportPrintStyles() {
  return (
    <style>{`
      @media print {
        .tam-report [data-print-hide] { display: none !important; }
        .tam-report { max-width: none; padding: 0; }
        .tam-report .report-block { break-inside: avoid; page-break-inside: avoid; }
        .tam-report .canvas-card { box-shadow: none !important; border: 1px solid #ddd; }
      }
    `}</style>
  );
}
