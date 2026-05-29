/**
 * ConceptDetailView — the concept page body. Renders the breadcrumb, an
 * editorial H1, the lede, a metadata strip, the disagreement view (one bar per
 * competing measurement), and a right rail of sibling concepts + a Build CTA.
 * The concept record is fetched by the parent; measurements are hydrated here
 * via useQueries so the disagreement bars stay in sync with /p detail data.
 */

"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { DisagreementView, toRows } from "@/components/concept/DisagreementBar";
import { NetworkGraphModal } from "@/components/network/NetworkGraphModal";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api-client";
import { lensLabel } from "@/lib/format";
import { conceptQuery, primitiveQuery } from "@/lib/queries";
import type { PrimitiveDetail } from "@/lib/schemas";

export function ConceptDetailView({ slug }: { slug: string }) {
  const concept = useQuery(conceptQuery(slug));
  const [networkOpen, setNetworkOpen] = useState(false);

  // Hydrate every measurement primitive so the disagreement view can scale and
  // tier-color the bars. Order-stable: combine maps in measurement order.
  const measurementSlugs = concept.data?.measurements ?? [];
  const measurementResults = useQueries({
    queries: measurementSlugs.map((s) => primitiveQuery(s)),
    combine: (results) => ({
      rows: toRows(results.map((r) => r.data).filter((d): d is PrimitiveDetail => d !== undefined)),
      loading: results.some((r) => r.isPending),
    }),
  });

  if (concept.isPending) return <DetailSkeleton />;

  if (concept.error) {
    if (concept.error instanceof ApiError && concept.error.status === 404) {
      return (
        <NotFoundState
          label="Concept"
          slug={slug}
          action={
            <Link href="/c">
              <Button variant="ghost" sm>
                Browse concepts
              </Button>
            </Link>
          }
        />
      );
    }
    return <ErrorState error={concept.error} onRetry={() => concept.refetch()} />;
  }

  const c = concept.data;
  const measurementCount = c.measurements.length;

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <nav aria-label="Breadcrumb" className="font-mono text-[12px] text-[var(--fg-3)]">
          <Link href="/c" className="hover:text-[var(--accent)] transition-colors">
            Concepts
          </Link>
          <span className="mx-1.5 text-[var(--fg-4)]">›</span>
          <span className="text-[var(--fg-2)]">{c.slug}</span>
        </nav>
      </header>

      <div className="flex-1 flex flex-col md:flex-row gap-8 px-8 py-8 max-w-[1280px] mx-auto w-full">
        <section className="flex-1 flex flex-col gap-6 min-w-0">
          <div className="flex flex-col gap-3">
            <h1 className="display text-[40px] leading-[1.05] text-[var(--fg-1)]">{c.name}</h1>
            <p className="max-w-[640px] whitespace-pre-line text-[15px] text-[var(--fg-2)] leading-relaxed">
              {c.definition}
            </p>
          </div>

          <MetadataStrip
            lens={lensLabel(c.analysis_lens.primary)}
            secondary={c.analysis_lens.secondary ? lensLabel(c.analysis_lens.secondary) : null}
            measurements={measurementCount}
            clearance={c.requires_clearance}
          />

          {c.requires_clearance.length > 0 ? (
            <ClearanceBanner clearance={c.requires_clearance} />
          ) : null}

          {measurementCount === 0 ? (
            <EmptyState
              title="No measurements yet"
              description="This concept has no attached primitives, so there is no disagreement view to show yet."
            />
          ) : measurementResults.loading ? (
            <Skeleton className="h-[280px]" />
          ) : (
            <DisagreementView rows={measurementResults.rows} />
          )}
        </section>

        <aside className="w-full md:w-[320px] md:shrink-0 flex flex-col gap-4">
          <Link href={`/build?q=${encodeURIComponent(c.slug)}`} className="block">
            <Button className="w-full justify-center">Build a TAM</Button>
          </Link>

          <Button
            variant="ghost"
            className="w-full justify-center"
            onClick={() => setNetworkOpen(true)}
          >
            Related entities
          </Button>

          <RailSection title="Sibling concepts">
            {c.competing_concepts.length === 0 ? (
              <p className="text-[13px] text-[var(--fg-3)]">No competing concepts recorded.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {c.competing_concepts.map((sib) => (
                  <li key={sib}>
                    <Link
                      href={`/c/${sib}`}
                      className="flex items-center justify-between gap-2 rounded-[var(--r-2)] px-2 py-1.5 text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)] hover:text-[var(--accent)] transition-colors"
                    >
                      <span className="truncate">{sib}</span>
                      <span className="text-[var(--fg-4)]">→</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </RailSection>
        </aside>
      </div>

      <NetworkGraphModal
        rootSlug={c.slug}
        rootName={c.name}
        open={networkOpen}
        onClose={() => setNetworkOpen(false)}
      />
    </main>
  );
}

function MetadataStrip({
  lens,
  secondary,
  measurements,
  clearance,
}: {
  lens: string;
  secondary: string | null;
  measurements: number;
  clearance: string[];
}) {
  return (
    <dl className="flex flex-wrap gap-x-10 gap-y-4 border-y border-[var(--border-1)] py-4">
      <Stat label="Primary lens" value={lens} />
      {secondary ? <Stat label="Secondary lens" value={secondary} /> : null}
      <Stat label="Measurements" value={String(measurements)} mono />
      <Stat label="Clearance" value={clearance.length > 0 ? "Required" : "Open"} />
    </dl>
  );
}

function Stat({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">{label}</dt>
      <dd className={`text-[15px] text-[var(--fg-1)] ${mono ? "tam-num tabular-nums" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function ClearanceBanner({ clearance }: { clearance: string[] }) {
  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-[var(--r-3)] bg-[var(--tier-analyst-tint)] px-4 py-3 text-[13px] text-[var(--fg-2)]"
    >
      <span className="font-medium text-[var(--tier-analyst)]">Requires clearance</span>
      <span>{clearance.join(", ")}</span>
    </div>
  );
}

function RailSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="canvas-card flex flex-col gap-2 p-4" style={{ borderRadius: "var(--r-3)" }}>
      <h2 className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">{title}</h2>
      {children}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <main className="flex-1 flex flex-col">
      <div className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="flex-1 flex flex-col md:flex-row gap-8 px-8 py-8 max-w-[1280px] mx-auto w-full">
        <section className="flex-1 flex flex-col gap-6 min-w-0">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-[280px] w-full" />
        </section>
        <aside className="w-full md:w-[320px] md:shrink-0 flex flex-col gap-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </aside>
      </div>
    </main>
  );
}
