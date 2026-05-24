"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const SUGGESTIONS = [
  "Doc-gen tooling for P&C insurance carriers, US",
  "Stripe TAM",
  "AI agents marketplace 2027",
];

export default function Landing() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/build?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-6 flex items-center justify-between">
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

      <section className="flex-1 flex flex-col items-center justify-center px-8 -mt-16">
        <h1 className="display text-[48px] md:text-[64px] text-center max-w-[820px] text-[var(--fg-1)]">
          A defensible{" "}
          <em className="text-[var(--accent)] not-italic font-display italic">TAM</em>{" "}
          in four minutes.
        </h1>
        <p className="mt-6 text-[15px] text-[var(--fg-2)] text-center max-w-[560px]">
          Type any market. Strata picks the frameworks, pre-fills the primitives, and shows you
          the range with sources you can cite in a memo.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(query);
          }}
          className="mt-12 w-full max-w-[640px]"
        >
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Doc-gen tooling for P&C insurance carriers, US"
              autoFocus
              className="w-full h-[56px] pl-5 pr-32 rounded-[var(--r-3)]
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
        </form>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-[12px] text-[var(--fg-3)]">
          <span>Try:</span>
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => {
                setQuery(suggestion);
                submit(suggestion);
              }}
              className="px-3 py-1 rounded-[var(--r-round)] bg-[var(--bg-2)]
                         text-[var(--fg-2)] hover:bg-[var(--bg-3)] hover:text-[var(--fg-1)]
                         transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      <footer className="px-8 py-6 text-[12px] text-[var(--fg-3)] flex items-center justify-between">
        <span>v0.2.0a — backend in progress</span>
        <span className="tracking-[0.25em] uppercase">github · for · TAM</span>
      </footer>
    </main>
  );
}

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
