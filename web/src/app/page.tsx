"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { ConceptCard } from "@/components/ConceptCard";
import { InterpretationCard, type InterpretationMatch } from "@/components/InterpretationCard";
import { TamCard, type TamSummary } from "@/components/TamCard";
import { StatBlock } from "@/components/ui/StatBlock";
import { formatUSD } from "@/lib/format";
import { rankByQuery } from "@/lib/fuzzy";
import { conceptsQuery } from "@/lib/queries";

// Static placeholder TAMs — replaced by /tam list endpoint in v0.4.
const RECENT_TAMS: TamSummary[] = [
  {
    state_hash: "3f7a9c8e0000000000000000000000000000000000000000000000000000face",
    concept_name: "Doc-gen tooling for P&C insurance carriers, US",
    low: 11_000_000,
    high: 497_000_000,
    created_at: "2026-05-21T00:00:00Z",
    lens: "cost_efficiency",
  },
  {
    state_hash: "a1b2c3d400000000000000000000000000000000000000000000000000000001",
    concept_name: "AI agents marketplace 2027",
    low: 2_400_000_000,
    high: 18_000_000_000,
    created_at: "2026-05-20T00:00:00Z",
    lens: "platform_throughput",
  },
  {
    state_hash: "b5e6f7a800000000000000000000000000000000000000000000000000000002",
    concept_name: "Stripe TAM — two-sided payments",
    low: 48_000_000_000,
    high: 220_000_000_000,
    created_at: "2026-05-18T00:00:00Z",
    lens: "platform_throughput",
  },
];

// Site-wide stats — replaced by /stats endpoint in v0.4.
const SITE_STATS = { concepts: 30, primitives: 350, frameworks: 5, sources: 87 };

function Logo() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 1200 800"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M 0 -160 L 180 140 L -180 140 Z"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="60"
        strokeLinejoin="round"
        transform="translate(600 400)"
      />
      <circle cx="600" cy="330" r="80" fill="var(--accent)" />
      <circle cx="510" cy="480" r="80" fill="var(--fg-1)" />
      <circle cx="690" cy="480" r="80" fill="var(--fg-1)" />
    </svg>
  );
}

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
  // navigator.platform is deprecated but still broadly available for this cosmetic hint.
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return (
    <span className="text-[11px] text-[var(--fg-4)] flex items-center gap-1">
      <kbd className="font-mono bg-[var(--bg-2)] border border-[var(--border-2)] rounded px-1 py-0.5 text-[10px]">
        {isMac ? "⌘" : "Ctrl"}
      </kbd>
      <kbd className="font-mono bg-[var(--bg-2)] border border-[var(--border-2)] rounded px-1 py-0.5 text-[10px]">
        K
      </kbd>
      <span>to focus</span>
    </span>
  );
}

function ConceptGridSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {Array.from({ length: 8 }).map((_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton, never re-ordered
        <div key={i} className="canvas-card p-4 h-[120px] animate-pulse bg-[var(--bg-2)]" />
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
      <header className="relative z-10 w-full px-8 py-6 flex items-center justify-between">
        <a href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <Logo />
          <span className="display text-[20px] text-[var(--fg-1)]">Strata</span>
        </a>
        <nav className="flex items-center gap-6 text-[13px] text-[var(--fg-2)]">
          <a href="/data" className="hover:text-[var(--fg-1)] transition-colors">
            Data
          </a>
          <a href="/browse" className="hover:text-[var(--fg-1)] transition-colors">
            Browse
          </a>
          <a href="/contribute" className="hover:text-[var(--fg-1)] transition-colors">
            Contribute
          </a>
        </nav>
      </header>

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
            {Array.from({ length: 3 }).map((_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton, never re-ordered
              <div key={i} className="canvas-card h-[110px] animate-pulse bg-[var(--bg-2)]" />
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
      {/* Top nav */}
      <header className="relative z-10 w-full px-8 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Logo />
          <span className="display text-[20px] text-[var(--fg-1)]">Strata</span>
        </div>
        <nav className="flex items-center gap-6 text-[13px] text-[var(--fg-2)]">
          <a href="/data" className="hover:text-[var(--fg-1)] transition-colors">
            Data
          </a>
          <a href="/browse" className="hover:text-[var(--fg-1)] transition-colors">
            Browse
          </a>
          <a href="/contribute" className="hover:text-[var(--fg-1)] transition-colors">
            Contribute
          </a>
        </nav>
      </header>

      {/* Hero */}
      <section className="flex flex-col items-center justify-center px-8 pt-16 pb-10">
        <h1 className="display text-[48px] md:text-[64px] text-center max-w-[820px] text-[var(--fg-1)]">
          A defensible <em className="text-[var(--accent)] not-italic font-display italic">TAM</em>{" "}
          in four minutes.
        </h1>
        <p className="mt-6 text-[15px] text-[var(--fg-2)] text-center max-w-[560px]">
          Type any market. Strata picks the frameworks, pre-fills the primitives, and shows you the
          range with sources you can cite in a memo.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(inputValue);
          }}
          className="mt-10 w-full max-w-[640px]"
        >
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Doc-gen tooling for P&C insurance carriers, US"
              // biome-ignore lint/a11y/noAutofocus: intentional — search is the page's only purpose
              autoFocus
              aria-label="Market sizing query"
              className="w-full h-[56px] pl-5 pr-36 rounded-[var(--r-3)]
                         bg-[var(--bg-1)] border border-[var(--border-2)]
                         text-[15px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)]
                         shadow-[var(--shadow-pop)]
                         focus:border-[var(--accent)] transition-colors"
            />
            <button
              type="submit"
              className="absolute right-1.5 top-1.5 h-[44px] px-5 rounded-[var(--r-2)]
                         bg-[var(--accent)] text-[var(--accent-fg-on)]
                         text-[13px] font-medium tracking-[-0.01em]
                         hover:bg-[var(--accent-hover)] active:bg-[var(--accent-active)]
                         transition-colors"
            >
              Size it →
            </button>
          </div>
          <div className="mt-2 flex justify-end pr-1">
            <KbdHint />
          </div>
        </form>
      </section>

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
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {concepts.slice(0, 8).map((c) => (
              <ConceptCard key={c.slug} concept={c} />
            ))}
          </div>
        )}
      </section>

      {/* Recently updated TAMs */}
      <section className="px-8 pb-10 max-w-[1280px] mx-auto w-full">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)] mb-4">
          Recently updated
        </h2>
        <div className="flex flex-col gap-2">
          {RECENT_TAMS.map((tam) => (
            <TamCard key={tam.state_hash} tam={tam} />
          ))}
        </div>
      </section>

      {/* Pyramid CTA */}
      <section
        className="mx-8 mb-10 max-w-[1280px] xl:mx-auto rounded-[var(--r-4)]
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

      {/* Stats footer */}
      <footer className="px-8 py-8 border-t border-[var(--border-1)]">
        <div className="max-w-[1280px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <StatBlock value={SITE_STATS.concepts} label="Concepts" />
            <StatBlock value={`${SITE_STATS.primitives}+`} label="Primitives" />
            <StatBlock value={SITE_STATS.frameworks} label="Frameworks" />
            <StatBlock value={SITE_STATS.sources} label="Sources" />
          </div>
          <div className="text-center sm:text-right">
            <p className="text-[11px] text-[var(--fg-3)] uppercase tracking-[0.08em]">
              Widest range on record
            </p>
            <p className="tam-num text-[18px] text-[var(--fg-1)] mt-0.5">
              {formatUSD(RECENT_TAMS[2]?.low ?? 0)}
              <span className="text-[var(--fg-4)] mx-1 font-sans font-normal">–</span>
              {formatUSD(RECENT_TAMS[2]?.high ?? 0)}
            </p>
          </div>
        </div>
        <div
          className="max-w-[1280px] mx-auto mt-6 pt-4 border-t border-[var(--border-1)]
                     flex items-center justify-between text-[11px] text-[var(--fg-4)]"
        >
          <span>v0.3.0 — backend live</span>
          <span className="tracking-[0.2em] uppercase">
            <a href="https://github.com" className="hover:text-[var(--fg-2)] transition-colors">
              GitHub
            </a>
            {" · "}
            <a href="/contribute" className="hover:text-[var(--fg-2)] transition-colors">
              Contribute
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
