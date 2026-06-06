"use client";

// Portfolio (/portfolio). Read-only view of a fund's companies linked to the
// org and sized against the sourced market bank. Every number here is computed
// OFFLINE and cached (no live LLM/Exa on this path) — sized rows link to the
// interactive build for their market; "unsizable" rows are intentional and show
// WHY we refuse to invent a number (the Q20 thesis, made visible).
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatUSD } from "@/lib/format";
import { portfolioQuery } from "@/lib/queries";
import type { PortfolioCompany } from "@/lib/schemas";

// Status badge: AA-legible text "ink" on the soft tint (the bare semantic hues
// read at only 1.6–2.4:1 on their own wash — see /impeccable audit).
const STATUS_BADGE: Record<string, { text: string; bg: string }> = {
  sized: { text: "var(--success-ink)", bg: "var(--ok-soft)" },
  unsized: { text: "var(--fg-2)", bg: "var(--bg-3)" },
  unsizable: { text: "var(--warning-ink)", bg: "var(--warn-soft)" },
};

export default function PortfolioPage() {
  const q = useQuery(portfolioQuery);

  const { sized, unsizable, counts } = useMemo(() => {
    const rows = q.data?.companies ?? [];
    return {
      sized: rows
        .filter((c) => c.status === "sized")
        .sort((a, b) => (b.tam_value ?? 0) - (a.tam_value ?? 0)),
      unsizable: rows.filter((c) => c.status === "unsizable"),
      counts: q.data?.counts ?? {},
    };
  }, [q.data]);

  return (
    <main className="flex flex-1 flex-col">
      <ListHeader
        title="Portfolio"
        count={q.data?.companies.length ?? 0}
        filter=""
        onFilter={() => {}}
        placeholder=""
      />

      <div className="mx-auto w-full max-w-[1100px] flex-1 px-8 py-8">
        {/* What this page is, stated plainly. */}
        <div className="mb-7 rounded-[var(--r-3)] border border-[var(--border-2)] bg-[var(--bg-2)] px-5 py-4">
          <div className="text-[13px] leading-relaxed text-[var(--fg-2)]">
            <span className="font-medium text-[var(--fg-1)]">Your portfolio, sized.</span> A company
            does not have a TAM — the market it competes in does. Each company below points at a
            shared, sourced market concept; the TAM is the median of that market&apos;s satisfiable
            scenarios. Every figure is pre-computed offline and hash-pinned — this page never calls
            an LLM. Companies we cannot defensibly size are shown as{" "}
            <span className="font-medium text-[var(--warning-ink)]">unsizable</span>, with the
            reason: we refuse to invent a number.
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] text-[var(--fg-2)]">
            {["company", "market concept", "sourced primitives", "framework", "TAM"].map(
              (step, i) => (
                <span key={step} className="flex items-center gap-2">
                  {i > 0 ? <span className="text-[var(--fg-4)]">→</span> : null}
                  <span className="rounded-[var(--r-round)] bg-[var(--bg-3)] px-2 py-0.5">
                    {step}
                  </span>
                </span>
              ),
            )}
          </div>
        </div>

        {q.isPending ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder
              <Skeleton key={i} className="h-[52px]" />
            ))}
          </div>
        ) : q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : (q.data?.companies.length ?? 0) === 0 ? (
          <EmptyState title="No companies" description="The portfolio is empty." />
        ) : (
          <>
            <div className="mb-4 flex flex-wrap gap-4 font-mono text-[11px] text-[var(--fg-2)]">
              <Stat label="total" value={counts.total ?? 0} />
              <Stat label="sized" value={counts.sized ?? 0} token="var(--success-ink)" />
              <Stat label="unsizable" value={counts.unsizable ?? 0} token="var(--warning-ink)" />
            </div>

            <SectionLabel>Sized · {sized.length}</SectionLabel>
            <ul
              aria-label="Sized companies"
              className="mt-3 overflow-hidden rounded-[var(--r-3)] border border-[var(--border-2)]"
            >
              {sized.map((c) => (
                <CompanyRow key={c.domain || c.name} company={c} />
              ))}
            </ul>

            {unsizable.length > 0 ? (
              <>
                <SectionLabel className="mt-9">
                  Unsizable · {unsizable.length} — honest by design
                </SectionLabel>
                <p className="mt-1 text-[12px] text-[var(--fg-3)]">
                  We have no sourced framework for these markets yet, so we refuse to fabricate a
                  TAM. Each reason is a proven gap that drives which lens we build next.
                </p>
                <ul
                  aria-label="Unsizable companies"
                  className="mt-3 overflow-hidden rounded-[var(--r-3)] border border-[var(--border-2)]"
                >
                  {unsizable.map((c) => (
                    <CompanyRow key={c.domain || c.name} company={c} />
                  ))}
                </ul>
              </>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}

function Stat({ label, value, token }: { label: string; value: number; token?: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="tabular-nums text-[13px] text-[var(--fg-1)]" style={{ color: token }}>
        {value.toLocaleString()}
      </span>
      <span className="uppercase tracking-[0.08em]">{label}</span>
    </span>
  );
}

function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h2
      className={`font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--fg-3)] ${className ?? ""}`}
    >
      {children}
    </h2>
  );
}

function CompanyRow({ company: c }: { company: PortfolioCompany }) {
  const badge = STATUS_BADGE[c.status] ?? { text: "var(--fg-2)", bg: "var(--bg-3)" };
  const sized = c.status === "sized" && c.market_concept_slug;
  // The market slug (sized) / reason (unsizable): shown in the side column on
  // sm+; on mobile it reflows under the name so the row never *drops* it (the
  // reason is the whole point of an unsizable row).
  const aside = sized ? c.market_concept_slug : c.reason;

  const inner = (
    <div className="flex min-h-[52px] items-center gap-4 border-b border-[var(--border-1)] bg-[var(--bg-1)] px-4 py-3 last:border-b-0 hover:bg-[var(--bg-2)]">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[14px] font-medium text-[var(--fg-1)]">{c.name}</span>
          {c.has_analyst_input ? (
            <span
              className="rounded-[var(--r-round)] px-1.5 py-0.5 font-mono text-[9px] uppercase"
              style={{ color: "var(--warning-ink)", background: "var(--warn-soft)" }}
              title="Contains unverified analyst inputs"
            >
              analyst
            </span>
          ) : null}
        </div>
        <div className="truncate font-mono text-[11px] text-[var(--fg-3)]">
          {c.domain}
          {c.vertical ? ` · ${c.vertical}` : ""}
        </div>
        {/* Mobile fallback for the aside (sm:hidden so it never duplicates). */}
        {aside ? (
          <div
            className={`mt-1 text-[11px] leading-snug sm:hidden ${
              sized ? "font-mono text-[var(--accent-active)]" : "text-[var(--fg-2)]"
            }`}
          >
            {aside}
          </div>
        ) : null}
      </div>

      {sized ? (
        <div className="hidden font-mono text-[11px] text-[var(--accent-active)] sm:block">
          {c.market_concept_slug}
        </div>
      ) : (
        <div className="hidden max-w-[440px] text-[11px] leading-snug text-[var(--fg-2)] sm:block">
          {c.reason}
        </div>
      )}

      <div className="w-[120px] text-right">
        {c.tam_value ? (
          <span className="tabular-nums text-[14px] font-medium text-[var(--fg-1)]">
            {formatUSD(c.tam_value)}
          </span>
        ) : (
          <span
            className="rounded-[var(--r-round)] px-2 py-0.5 font-mono text-[10px] uppercase"
            style={{ color: badge.text, background: badge.bg }}
          >
            {c.status}
          </span>
        )}
      </div>
    </div>
  );

  // Sized rows link to the interactive build for their market (always renders
  // for a registry concept); unsizable rows are not links.
  return (
    <li>
      {sized ? (
        <Link
          href={`/build/${c.market_concept_slug}`}
          className="block"
          aria-label={`${c.name} — open ${c.market_concept_slug} market build`}
        >
          {inner}
        </Link>
      ) : (
        inner
      )}
    </li>
  );
}
