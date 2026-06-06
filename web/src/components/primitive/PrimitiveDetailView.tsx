/**
 * PrimitiveDetailView — the primitive page body. Atomic primitives render their
 * value, source snapshot (url + hash + tier), methodology, lineage, geography,
 * distribution/delivery, and uncertainty. Composite primitives have no own
 * source — they're set-ops over other primitives — so that branch renders the
 * input list + set operation instead. The discriminated `kind` field drives
 * which sections appear.
 *
 * Note: the live data layer has 0 composite primitives at v0.2 (all 355 are
 * atomic). The composite branch is built to schema so it lights up the moment
 * a composite is seeded, but it is currently untested against real data.
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { TierBadge } from "@/components/ui/TierBadge";
import { ApiError } from "@/lib/api-client";
import { PLACEHOLDER_SNAPSHOT_LABEL, formatCompact, isPlaceholderSnapshot } from "@/lib/format";
import { primitiveQuery } from "@/lib/queries";
import type {
  AtomicPrimitive,
  CompositePrimitive,
  Geo,
  PrimitiveDetail,
  Unit,
} from "@/lib/schemas";

export function PrimitiveDetailView({ slug }: { slug: string }) {
  const primitive = useQuery(primitiveQuery(slug));

  if (primitive.isPending) return <DetailSkeleton />;

  if (primitive.error) {
    if (primitive.error instanceof ApiError && primitive.error.status === 404) {
      return (
        <NotFoundState
          label="Primitive"
          slug={slug}
          action={
            <Link href="/p">
              <Button variant="ghost" sm>
                Browse primitives
              </Button>
            </Link>
          }
        />
      );
    }
    return <ErrorState error={primitive.error} onRetry={() => primitive.refetch()} />;
  }

  const p = primitive.data;

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <nav aria-label="Breadcrumb" className="font-mono text-[12px] text-[var(--fg-3)]">
          <Link href="/p" className="hover:text-[var(--accent)] transition-colors">
            Primitives
          </Link>
          <span className="mx-1.5 text-[var(--fg-4)]">›</span>
          <span className="text-[var(--fg-2)]">{p.slug}</span>
        </nav>
      </header>

      <div className="flex-1 px-8 py-8 max-w-[900px] mx-auto w-full flex flex-col gap-8">
        <PrimitiveHeader primitive={p} />
        {p.kind === "atomic_primitive" ? <AtomicSections p={p} /> : <CompositeSections p={p} />}
      </div>
    </main>
  );
}

function PrimitiveHeader({ primitive }: { primitive: PrimitiveDetail }) {
  const atomic = primitive.kind === "atomic_primitive" ? primitive : null;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <h1 className="display text-[32px] leading-[1.1] text-[var(--fg-1)]">{primitive.name}</h1>
        {atomic ? <TierBadge tier={atomic.source.tier} className="mt-2 shrink-0" /> : null}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        {atomic ? (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
              Value
            </span>
            <span className="tam-num text-[36px] text-[var(--fg-1)] tabular-nums">
              {formatCompact(atomic.value, atomic.unit)}
            </span>
          </div>
        ) : (
          <span className="role-chip role-chip--accent uppercase tracking-[0.04em]">Composite</span>
        )}
        <UnitChip unit={primitive.unit} />
        {atomic ? (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
              As of
            </span>
            <span className="font-mono text-[13px] text-[var(--fg-2)]">{atomic.as_of}</span>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
              As of
            </span>
            <span className="font-mono text-[13px] text-[var(--fg-2)]">{primitive.as_of}</span>
          </div>
        )}
      </div>

      <Link
        href={`/c/${primitive.concept_slug}`}
        className="self-start text-[13px] text-[var(--accent)] hover:underline"
      >
        ↳ {primitive.concept_slug}
      </Link>
    </div>
  );
}

function AtomicSections({ p }: { p: AtomicPrimitive }) {
  return (
    <>
      <Section title="Methodology">
        <p className="whitespace-pre-line text-[14px] text-[var(--fg-2)] leading-relaxed">
          {p.description}
        </p>
      </Section>

      <Section title="Source snapshot">
        <dl className="flex flex-col gap-3">
          <Field label="Source">
            <a
              href={p.source.url}
              target="_blank"
              rel="noreferrer"
              className="break-all text-[var(--accent)] hover:underline"
            >
              {p.source.url}
            </a>
          </Field>
          <Field label="Tier">
            <TierBadge tier={p.source.tier} />
          </Field>
          <Field label="Accessed">
            <span className="font-mono text-[var(--fg-2)]">{p.source.accessed}</span>
          </Field>
          <Field label="Snapshot SHA-256">
            {isPlaceholderSnapshot(p.source.snapshot_sha256) ? (
              <span className="text-[12px] text-[var(--fg-3)]">{PLACEHOLDER_SNAPSHOT_LABEL}</span>
            ) : (
              <code className="break-all font-mono text-[12px] text-[var(--fg-2)]">
                {p.source.snapshot_sha256}
              </code>
            )}
          </Field>
          {p.source.original_publisher ? (
            <Field label="Original publisher">
              <span className="text-[var(--fg-2)]">{p.source.original_publisher}</span>
            </Field>
          ) : null}
          {p.source.paraphrase_text ? (
            <Field label="Paraphrase">
              <span className="text-[var(--fg-2)] italic">“{p.source.paraphrase_text}”</span>
            </Field>
          ) : null}
        </dl>
      </Section>

      <Section title="Geography">
        <GeoBlock geo={p.geo} perspective={p.geo_perspective} />
      </Section>

      <Section title="Distribution & delivery">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Distribution">
            <span className="text-[var(--fg-2)]">{p.distribution_shape}</span>
          </Field>
          <Field label="Delivery mode">
            <span className="text-[var(--fg-2)]">{p.delivery_mode}</span>
          </Field>
          {p.expiry ? (
            <Field label="Expiry">
              <span className="font-mono text-[var(--fg-2)]">{p.expiry}</span>
            </Field>
          ) : null}
        </dl>
      </Section>

      {p.uncertainty ? (
        <Section title="Uncertainty">
          <dl className="flex flex-col gap-3">
            <Field label="Range">
              <span className="font-mono text-[var(--fg-2)] tabular-nums">
                {formatCompact(p.uncertainty.range[0], p.unit)} —{" "}
                {formatCompact(p.uncertainty.range[1], p.unit)}
              </span>
            </Field>
            <Field label="Basis">
              <span className="text-[var(--fg-2)]">{p.uncertainty.basis}</span>
            </Field>
          </dl>
        </Section>
      ) : null}

      {p.derives_from.length > 0 ? (
        <Section title="Lineage">
          <ul className="flex flex-col gap-1">
            {p.derives_from.map((dep) => (
              <li key={dep}>
                <Link
                  href={`/p/${dep}`}
                  className="text-[13px] text-[var(--accent)] hover:underline"
                >
                  {dep}
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </>
  );
}

function CompositeSections({ p }: { p: CompositePrimitive }) {
  return (
    <>
      <Section title="Methodology">
        <p className="whitespace-pre-line text-[14px] text-[var(--fg-2)] leading-relaxed">
          {p.description}
        </p>
      </Section>

      <Section title="Composition">
        <dl className="flex flex-col gap-3">
          <Field label="Set operation">
            <span className="role-chip uppercase tracking-[0.04em]">
              {p.set_operation.replace(/_/g, " ")}
            </span>
          </Field>
          {p.tag_filter ? (
            <Field label="Tag filter">
              <code className="font-mono text-[var(--fg-2)]">{p.tag_filter}</code>
            </Field>
          ) : null}
        </dl>
      </Section>

      <Section title="Inputs">
        {p.inputs.length === 0 ? (
          <p className="text-[13px] text-[var(--fg-3)]">No inputs recorded.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {p.inputs.map((dep) => (
              <li key={dep}>
                <Link
                  href={`/p/${dep}`}
                  className="text-[13px] text-[var(--accent)] hover:underline"
                >
                  {dep}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Geography">
        <GeoBlock geo={p.geo} perspective={p.geo_perspective} />
      </Section>
    </>
  );
}

function GeoBlock({ geo, perspective }: { geo: Geo; perspective: string }) {
  return (
    <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
      <Field label="Level">
        <span className="text-[var(--fg-2)]">{geo.level}</span>
      </Field>
      <Field label="Codes">
        <span className="font-mono text-[var(--fg-2)]">{geo.codes.join(", ") || "—"}</span>
      </Field>
      <Field label="Perspective">
        <span className="text-[var(--fg-2)]">{perspective}</span>
      </Field>
    </dl>
  );
}

function UnitChip({ unit }: { unit: Unit }) {
  const parts = [unit.kind, unit.dimension, unit.currency, unit.denominator].filter(Boolean);
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">Unit</span>
      <span className="font-mono text-[13px] text-[var(--fg-2)]">{parts.join(" · ")}</span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 border-t border-[var(--border-1)] pt-6">
      <h2 className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">{title}</h2>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-4)]">{label}</dt>
      <dd className="text-[13px]">{children}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <main className="flex-1 flex flex-col">
      <div className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="flex-1 px-8 py-8 max-w-[900px] mx-auto w-full flex flex-col gap-8">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-12 w-1/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </main>
  );
}
