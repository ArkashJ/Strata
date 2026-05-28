/**
 * FrameworkDetailView — the framework page body. A framework is the
 * unit-crossing arithmetic recipe (Q3): it declares typed inputs, a formula,
 * an output unit, and the concepts it applies to. Variants attach primitive
 * slugs (never scalar values — Q15) per scope. This view renders the formula
 * (prose + mono), an inputs table, the variant list (each linking its bound
 * primitives), applicability, and the horizon/clearance metadata.
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api-client";
import { lensLabel, tierLabel } from "@/lib/format";
import { frameworkQuery } from "@/lib/queries";
import type { FrameworkInput, FrameworkVariant, Unit } from "@/lib/schemas";

export function FrameworkDetailView({ slug }: { slug: string }) {
  const framework = useQuery(frameworkQuery(slug));

  if (framework.isPending) return <DetailSkeleton />;

  if (framework.error) {
    if (framework.error instanceof ApiError && framework.error.status === 404) {
      return (
        <NotFoundState
          label="Framework"
          slug={slug}
          action={
            <Link href="/f">
              <Button variant="ghost" sm>
                Browse frameworks
              </Button>
            </Link>
          }
        />
      );
    }
    return <ErrorState error={framework.error} onRetry={() => framework.refetch()} />;
  }

  const f = framework.data;

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <nav aria-label="Breadcrumb" className="font-mono text-[12px] text-[var(--fg-3)]">
          <Link href="/f" className="hover:text-[var(--accent)] transition-colors">
            Frameworks
          </Link>
          <span className="mx-1.5 text-[var(--fg-4)]">›</span>
          <span className="text-[var(--fg-2)]">{f.slug}</span>
        </nav>
      </header>

      <div className="flex-1 px-8 py-8 max-w-[900px] mx-auto w-full flex flex-col gap-8">
        <div className="flex flex-col gap-3">
          <h1 className="display text-[32px] leading-[1.1] text-[var(--fg-1)]">{f.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <span className="role-chip uppercase tracking-[0.04em]">
              {tierLabel(f.method_family)}
            </span>
            <span className="role-chip role-chip--accent uppercase tracking-[0.04em]">
              {lensLabel(f.lens)}
            </span>
          </div>
        </div>

        <Section title="Formula">
          <p className="text-[14px] text-[var(--fg-2)] leading-relaxed">
            Multiplies its inputs into a{" "}
            <span className="font-medium text-[var(--fg-1)]">{unitLabel(f.output_unit)}</span>{" "}
            output.
          </p>
          <code className="mt-1 block rounded-[var(--r-2)] bg-[var(--bg-2)] px-4 py-3 font-mono text-[13px] text-[var(--fg-1)]">
            {f.formula}
          </code>
        </Section>

        <Section title="Inputs">
          <InputsTable inputs={f.inputs} />
        </Section>

        <Section title="Variants">
          {f.variants.length === 0 ? (
            <p className="text-[13px] text-[var(--fg-3)]">No variants attached.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {f.variants.map((v) => (
                <VariantRow key={v.scope} variant={v} />
              ))}
            </ul>
          )}
        </Section>

        <Section title="Applicability">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <SlugColumn label="Applicable to" slugs={f.applicable_to} accent />
            <SlugColumn label="Not applicable to" slugs={f.not_applicable_to} />
          </div>
        </Section>

        <Section title="Horizon & clearance">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Field label="Horizon class">
              <span className="text-[var(--fg-2)]">{f.horizon_class.replace(/_/g, " ")}</span>
            </Field>
            <Field label="Expansion-stage param">
              <span className="text-[var(--fg-2)]">
                {f.expansion_stage_parameter ? "Yes" : "No"}
              </span>
            </Field>
            <Field label="Clearance">
              <span className="text-[var(--fg-2)]">
                {f.requires_clearance.length > 0 ? f.requires_clearance.join(", ") : "Open"}
              </span>
            </Field>
          </dl>
        </Section>
      </div>
    </main>
  );
}

function InputsTable({ inputs }: { inputs: FrameworkInput[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
            <th className="pb-2 pr-4 font-medium">Name</th>
            <th className="pb-2 pr-4 font-medium">Role</th>
            <th className="pb-2 pr-4 font-medium">Unit signature</th>
            <th className="pb-2 font-medium">Required</th>
          </tr>
        </thead>
        <tbody>
          {inputs.map((i) => (
            <tr key={i.name} className="border-t border-[var(--border-1)]">
              <td className="py-2.5 pr-4 font-mono text-[var(--fg-1)]">{i.name}</td>
              <td className="py-2.5 pr-4">
                <span className="role-chip uppercase tracking-[0.04em]">
                  {i.role.replace(/_/g, " ")}
                </span>
              </td>
              <td className="py-2.5 pr-4 font-mono text-[12px] text-[var(--fg-2)]">
                {unitLabel(i.unit_signature)}
              </td>
              <td className="py-2.5 text-[var(--fg-2)]">{i.required ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VariantRow({ variant }: { variant: FrameworkVariant }) {
  const bindings = Object.entries(variant.default_inputs);
  return (
    <li className="canvas-card flex flex-col gap-2 p-4" style={{ borderRadius: "var(--r-2)" }}>
      <Link
        href={`/c/${variant.scope}`}
        className="self-start font-mono text-[13px] text-[var(--accent)] hover:underline"
      >
        {variant.scope}
      </Link>
      <dl className="flex flex-col gap-1">
        {bindings.map(([role, primitiveSlug]) => (
          <div key={role} className="flex items-baseline gap-2 text-[12px]">
            <dt className="font-mono text-[var(--fg-3)]">{role}</dt>
            <span className="text-[var(--fg-4)]">→</span>
            <dd>
              <Link
                href={`/p/${primitiveSlug}`}
                className="font-mono text-[var(--accent)] hover:underline"
              >
                {primitiveSlug}
              </Link>
            </dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

function SlugColumn({
  label,
  slugs,
  accent = false,
}: {
  label: string;
  slugs: string[];
  accent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-4)]">{label}</h3>
      {slugs.length === 0 ? (
        <p className="text-[13px] text-[var(--fg-3)]">—</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {slugs.map((s) => (
            <li key={s}>
              <Link
                href={`/c/${s}`}
                className={`font-mono text-[12px] hover:underline ${
                  accent ? "text-[var(--accent)]" : "text-[var(--fg-2)] hover:text-[var(--accent)]"
                }`}
              >
                {s}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function unitLabel(unit: Unit): string {
  return [unit.kind, unit.dimension, unit.currency, unit.denominator].filter(Boolean).join(" · ");
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
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </main>
  );
}
