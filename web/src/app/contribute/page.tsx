import Link from "next/link";

// Contribution splash (/contribute · U6). NOTE: Strata is proprietary — the
// LICENSE reserves all rights to the Owner — so this is framed as a workflow for
// authorized collaborators, not a public open-source PR flow. The schema records
// referenced below are the load-bearing decision docs in the repo's docs/ tree;
// they are not web-served, so they are listed as paths rather than links.
export default function ContributePage() {
  return (
    <main className="flex flex-1 flex-col">
      <header className="w-full border-b border-[var(--border-1)] px-8 py-5">
        <div className="mx-auto flex max-w-[1280px] items-baseline gap-3">
          <Link
            href="/"
            className="display text-[20px] text-[var(--fg-1)] transition-colors hover:text-[var(--accent)]"
          >
            ← Strata
          </Link>
          <span className="text-[var(--fg-4)]">/</span>
          <h1 className="text-[15px] font-medium text-[var(--fg-1)]">Contribute</h1>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[760px] flex-1 px-8 py-12">
        <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)]">
          For authorized collaborators
        </p>
        <h2 className="display mt-2 text-[36px] leading-[1.1] text-[var(--fg-1)]">
          Help curate the <span className="italic">market-sizing</span> data bank
        </h2>
        <p className="mt-4 max-w-[560px] text-[15px] leading-relaxed text-[var(--fg-2)]">
          Strata is a curated engine for defensible TAMs: atomic, sourced primitives combined by
          transparent frameworks. Contributions sharpen the numbers and the recipes — every change
          is reviewed and content-hash pinned.
        </p>

        <section className="mt-10 grid gap-4 sm:grid-cols-2">
          <InfoCard title="Why contribute">
            A market size is only as good as its chain of custody. Adding a sourced primitive, a
            framework variant, or an expert annotation makes every TAM that cites it more
            defensible.
          </InfoCard>
          <InfoCard title="What you contribute">
            Atomic primitives (one source, one number, reproducible), composites (same-unit set
            ops), frameworks (unit-crossing recipes, no scalar defaults), and text-only annotations
            that never alter the math.
          </InfoCard>
        </section>

        <section className="mt-8">
          <h3 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)]">
            Record schemas
          </h3>
          <p className="mt-2 text-[13px] text-[var(--fg-3)]">
            Every record follows a locked schema. Read the decision records before authoring:
          </p>
          <ul className="mt-3 flex flex-col gap-1.5 text-[13px] text-[var(--fg-2)]">
            <SchemaRef
              path="docs/07-data-layer-brainstorm.md"
              desc="primitives, composites, frameworks, units, geo, source tiers"
            />
            <SchemaRef path="docs/08-product-surface-brainstorm.md" desc="pyramid + UX surface" />
            <SchemaRef
              path="docs/09-expert-layer-brainstorm.md"
              desc="annotation schema (commentary only)"
            />
          </ul>
        </section>

        <section className="mt-8 rounded-[var(--r-3)] border border-[var(--border-1)] bg-[var(--bg-1)] px-5 py-4">
          <h3 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)]">
            Licensing
          </h3>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--fg-2)]">
            Strata is proprietary and confidential — all rights reserved by the owner. No license to
            use, copy, or redistribute is granted. Access and contribution are by written permission
            only; submitted work is governed by your collaborator agreement, not an open-source
            license.
          </p>
        </section>

        <p className="mt-8 text-[13px] text-[var(--fg-3)]">
          A self-serve review pipeline (validator-gated submissions, automated review, and a web
          form for annotations) is planned for v0.5. Until then, coordinate contributions with the
          maintainer.
        </p>
      </div>
    </main>
  );
}

function InfoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="canvas-card flex flex-col gap-2 p-5" style={{ borderRadius: "var(--r-3)" }}>
      <h3 className="text-[14px] font-medium text-[var(--fg-1)]">{title}</h3>
      <p className="text-[13px] leading-relaxed text-[var(--fg-3)]">{children}</p>
    </div>
  );
}

function SchemaRef({ path, desc }: { path: string; desc: string }) {
  return (
    <li className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-2">
      <code className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[12px] text-[var(--fg-1)]">
        {path}
      </code>
      <span className="text-[var(--fg-3)]">— {desc}</span>
    </li>
  );
}
