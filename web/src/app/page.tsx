"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { ConceptCard } from "@/components/ConceptCard";
import { InterpretationCard, type InterpretationMatch } from "@/components/InterpretationCard";
import { TamCard, type TamSummary } from "@/components/TamCard";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Reveal } from "@/components/landing/Reveal";
import { StatBlock } from "@/components/ui/StatBlock";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import { formatUSD } from "@/lib/format";
import { rankByQuery } from "@/lib/fuzzy";
import { buildQuery, conceptsQuery, frameworksQuery, primitivesQuery } from "@/lib/queries";
import { tamRange } from "@/lib/tam";

// Fallback library counts shown until the live queries resolve (the real
// numbers come from conceptsQuery / primitivesQuery / frameworksQuery). `sources`
// has no list endpoint yet, so it stays the known seed count.
const SITE_STATS = {
  concepts: 30,
  primitives: 350,
  frameworks: 5,
  sources: 87,
};

function PyramidIllustration() {
  return (
    <svg
      width="120"
      height="80"
      viewBox="0 0 120 80"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="opacity-60"
    >
      <polygon points="60,4 110,74 10,74" fill="none" stroke="var(--border-2)" strokeWidth="2" />
      <line x1="10" y1="74" x2="110" y2="74" stroke="var(--border-2)" strokeWidth="1.5" />
      <line x1="35" y1="40" x2="85" y2="40" stroke="var(--border-2)" strokeWidth="1.5" />
      <circle cx="60" cy="4" r="4" fill="var(--accent)" />
      <circle cx="35" cy="40" r="4" fill="var(--fg-3)" />
      <circle cx="85" cy="40" r="4" fill="var(--fg-3)" />
      <circle cx="10" cy="74" r="4" fill="var(--fg-3)" />
      <circle cx="60" cy="74" r="4" fill="var(--fg-3)" />
      <circle cx="110" cy="74" r="4" fill="var(--fg-3)" />
    </svg>
  );
}

function KbdHint() {
  // navigator is undefined on the server, so the modifier glyph legitimately
  // differs between the server ("Ctrl") and the client ("⌘" on macOS). That is
  // a known, intentional mismatch — suppressHydrationWarning on the glyph tells
  // React not to flag it (the React-blessed pattern for platform/locale text).
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return (
    <span className="text-[11px] text-[var(--fg-4)] flex items-center gap-1">
      <kbd
        suppressHydrationWarning
        className="font-mono bg-[var(--bg-2)] border border-[var(--border-2)] rounded px-1 py-0.5 text-[10px]"
      >
        {isMac ? "⌘" : "Ctrl"}
      </kbd>
      <kbd className="font-mono bg-[var(--bg-2)] border border-[var(--border-2)] rounded px-1 py-0.5 text-[10px]">
        K
      </kbd>
      <span>to focus</span>
    </span>
  );
}

const GRID_SKELETON_KEYS = ["sk0", "sk1", "sk2", "sk3", "sk4", "sk5", "sk6", "sk7"];
const ROW_SKELETON_KEYS = ["row0", "row1", "row2"];

function ConceptGridSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {GRID_SKELETON_KEYS.map((key) => (
        <div key={key} className="canvas-card p-4 h-[120px] animate-pulse bg-[var(--bg-2)]" />
      ))}
    </div>
  );
}

// Shown when /?q= is present — fuzzy-matches the query against loaded concepts.
function InterpretationBranch({ rawQuery }: { rawQuery: string }) {
  const { data: concepts, isLoading } = useQuery(conceptsQuery);
  const router = useRouter();

  const matches: InterpretationMatch[] = concepts
    ? rankByQuery(concepts, rawQuery, (c) => `${c.name} ${c.definition}`)
        .slice(0, 5)
        .map(({ item, score }, i) => ({
          concept: item,
          scope: i === 0 ? "default" : i === 1 ? "broad" : ("narrow" as const),
          previewRange: null,
          score,
        }))
    : [];

  const handleDirect = () => router.push(`/build?q=${encodeURIComponent(rawQuery)}`);

  return (
    <main className="flex-1 flex flex-col">
      <section className="flex-1 px-8 py-10 max-w-[760px] mx-auto w-full">
        <div className="mb-8">
          <p className="text-[12px] text-[var(--fg-3)] mb-1">Interpreting your query</p>
          <h1 className="text-[22px] font-medium text-[var(--fg-1)] leading-snug">
            &ldquo;{rawQuery}&rdquo;
          </h1>
          <p className="mt-2 text-[13px] text-[var(--fg-2)]">
            Pick the closest concept below, or{" "}
            <button
              type="button"
              onClick={handleDirect}
              className="text-[var(--accent)] underline underline-offset-2 hover:no-underline"
            >
              size it directly
            </button>{" "}
            with live synthesis.
          </p>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-3">
            {ROW_SKELETON_KEYS.map((key) => (
              <div key={key} className="canvas-card h-[110px] animate-pulse bg-[var(--bg-2)]" />
            ))}
          </div>
        ) : matches.length === 0 ? (
          <div className="canvas-card p-6 text-center text-[var(--fg-3)] text-[13px]">
            No close registry matches —{" "}
            <button
              type="button"
              onClick={handleDirect}
              className="text-[var(--accent)] underline underline-offset-2"
            >
              size it with live synthesis
            </button>
          </div>
        ) : (
          <ul className="flex flex-col gap-3 list-none" aria-label="Interpretation options">
            {matches.map((m) => (
              <li key={m.concept.slug}>
                <InterpretationCard match={m} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function LandingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawQuery = searchParams.get("q") ?? "";

  const [inputValue, setInputValue] = useState(rawQuery);
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: concepts, isLoading } = useQuery(conceptsQuery);
  const { data: primitives } = useQuery(primitivesQuery);
  const { data: frameworks } = useQuery(frameworksQuery);

  // "Recently updated" used to be invented figures. The backend doesn't persist
  // TAMs, so instead of faking a list we size the first few real concepts live
  // via /build (which now persists each TAM to Postgres) and show their actual
  // ranges. Rows link to the frozen /tam/<hash> artifact — the shareable
  // permalink, durable across restarts (P0.1).
  const featuredSlugs = (concepts ?? []).slice(0, 3).map((c) => c.slug);
  const featuredBuilds = useQueries({
    queries: featuredSlugs.map((slug) => buildQuery(slug)),
  });
  const featuredTams = featuredBuilds.flatMap((b, i) => {
    // Correlate the build back to its concept by slug, not array index — a
    // background refetch could momentarily reorder `concepts` and mislabel a TAM.
    const concept = concepts?.find((c) => c.slug === featuredSlugs[i]);
    if (!b.data || !concept) return [];
    const { low, high } = tamRange(b.data);
    const tam: TamSummary = {
      state_hash: b.data.state_hash,
      concept_name: concept.name,
      low,
      high,
      created_at: b.data.created_at,
      lens: concept.primary_lens,
      independence_score: b.data.independence_score,
      method_families: b.data.method_families_used.length,
    };
    return [{ tam, href: `/tam/${tam.state_hash}` }];
  });
  const widestTam = [...featuredTams].map((f) => f.tam).sort((a, b) => b.high - a.high)[0];

  // ⌘K / Ctrl+K focuses the search input from anywhere on the page.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (rawQuery) {
    return <InterpretationBranch rawQuery={rawQuery} />;
  }

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/build?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <main className="flex-1 flex flex-col">
      {/* Animated hero — query box stays wired to the same submit/route path */}
      <Hero
        inputRef={inputRef}
        value={inputValue}
        onChange={setInputValue}
        onSubmit={(e) => {
          e.preventDefault();
          submit(inputValue);
        }}
        kbdHint={<KbdHint />}
      />

      {/* How it works — text-only explainer strip */}
      <HowItWorks />

      {/* Popular concepts grid */}
      <section className="px-8 pb-10 max-w-[1280px] mx-auto w-full">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)] mb-4">
          Popular concepts
        </h2>
        {isLoading ? (
          <ConceptGridSkeleton />
        ) : !concepts || concepts.length === 0 ? (
          <p className="text-[13px] text-[var(--fg-3)]">No concepts loaded yet.</p>
        ) : (
          <Stagger className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {concepts.slice(0, 8).map((c) => (
              <StaggerItem key={c.slug}>
                <ConceptCard concept={c} />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </section>

      {/* Featured TAMs — sized live from real concepts (live data preserved) */}
      <Reveal>
        <section className="px-8 pb-10 max-w-[1280px] mx-auto w-full">
          <h2 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)] mb-4">
            Featured TAMs
          </h2>
          <div className="flex flex-col gap-2">
            {featuredTams.length === 0 ? (
              <p className="text-[13px] text-[var(--fg-3)]">Sizing featured concepts…</p>
            ) : (
              <Stagger className="flex flex-col gap-2">
                {featuredTams.map(({ tam, href }) => (
                  <StaggerItem key={href}>
                    <TamCard tam={tam} href={href} />
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </div>
        </section>
      </Reveal>

      {/* Pyramid CTA */}
      <Reveal className="mx-8 mb-10 max-w-[1280px] xl:mx-auto">
        <section
          className="rounded-[var(--r-4)]
                   border border-[var(--border-1)] bg-[var(--bg-1)] px-8 py-8
                   flex flex-col md:flex-row items-center gap-6"
        >
          <PyramidIllustration />
          <div className="flex-1 text-center md:text-left">
            <p className="text-[14px] font-medium text-[var(--fg-1)]">Explore the data pyramid</p>
            <p className="mt-1 text-[12px] text-[var(--fg-3)] max-w-[480px]">
              Every TAM is built from atomic primitives — sourced numbers with a chain of custody.
              Browse the pyramid to see how they compose into frameworks and outputs.
            </p>
          </div>
          <a
            href="/graph"
            className="shrink-0 h-[36px] px-5 rounded-[var(--r-2)]
                     border border-[var(--border-2)] bg-[var(--bg-0)]
                     text-[13px] font-medium text-[var(--fg-1)]
                     hover:bg-[var(--bg-2)] transition-colors
                     flex items-center"
          >
            Open graph →
          </a>
        </section>
      </Reveal>

      {/* Stats footer */}
      <footer className="px-8 py-8 border-t border-[var(--border-1)]">
        <div className="max-w-[1280px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <StatBlock value={concepts?.length ?? SITE_STATS.concepts} label="Concepts" />
            <StatBlock
              value={`${primitives?.length ?? SITE_STATS.primitives}`}
              label="Primitives"
            />
            <StatBlock value={frameworks?.length ?? SITE_STATS.frameworks} label="Frameworks" />
            <StatBlock value={SITE_STATS.sources} label="Sources" />
          </div>
          {widestTam ? (
            <div className="text-center sm:text-right">
              <p className="text-[11px] text-[var(--fg-3)] uppercase tracking-[0.08em]">
                Widest range featured
              </p>
              <p className="tam-num text-[18px] text-[var(--fg-1)] mt-0.5">
                {formatUSD(widestTam.low)}
                <span className="text-[var(--fg-4)] mx-1 font-sans font-normal">–</span>
                {formatUSD(widestTam.high)}
              </p>
            </div>
          ) : null}
        </div>
        <div
          className="max-w-[1280px] mx-auto mt-6 pt-4 border-t border-[var(--border-1)]
                     flex items-center justify-between text-[11px] text-[var(--fg-4)]"
        >
          <span>v0.4.0 — backend live</span>
          <span className="tracking-[0.2em] uppercase">
            <a
              href="https://github.com/ArkashJ/Strata"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[var(--fg-2)] transition-colors"
            >
              GitHub
            </a>
          </span>
        </div>
      </footer>
    </main>
  );
}

// Suspense required because useSearchParams() needs it in the Next.js app router.
export default function Landing() {
  return (
    <Suspense>
      <LandingContent />
    </Suspense>
  );
}
