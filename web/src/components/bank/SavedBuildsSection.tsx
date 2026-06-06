"use client";

/**
 * SavedBuildsSection — brings over the dashboard's favorites + saved-build
 * history panels, now living under My Bank. The two lists render in order:
 *
 *   1. Favorites — pinned across visits via Zustand + localStorage
 *   2. Recent builds — the per-browser state-hash history (capped by build-history)
 *
 * Auth-gating: when Clerk is configured, the recent-builds list requires
 * sign-in (the user's identity is part of the history contract). Favorites are
 * always shown — they are pinned locally and don't need an identity.
 */

import { Show, SignInButton } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";

import { FavoriteStar } from "@/components/FavoriteStar";
import { Skeleton } from "@/components/ui/Skeleton";
import { type BuildHistoryEntry, readBuildHistory } from "@/lib/build-history";
import { clerkEnabled } from "@/lib/clerk";
import { useHasMounted } from "@/lib/use-has-mounted";
import { useFavoritesStore } from "@/stores/favorites-store";

// ── Shared helpers ────────────────────────────────────────────────────────────

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const DIVISIONS: { amount: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { amount: 60, unit: "second" },
  { amount: 60, unit: "minute" },
  { amount: 24, unit: "hour" },
  { amount: 7, unit: "day" },
  { amount: 4.34524, unit: "week" },
  { amount: 12, unit: "month" },
  { amount: Number.POSITIVE_INFINITY, unit: "year" },
];

function relativeTime(input: number | string): string {
  const normalized =
    typeof input === "string" && !/[Z+]|-\d\d:\d\d$/.test(input) ? `${input}Z` : input;
  const ms = typeof normalized === "number" ? normalized : Date.parse(normalized);
  if (!Number.isFinite(ms)) return "";
  let duration = (ms - Date.now()) / 1000;
  for (const div of DIVISIONS) {
    if (Math.abs(duration) < div.amount) {
      return rtf.format(Math.round(duration), div.unit);
    }
    duration /= div.amount;
  }
  return "";
}

// ── Build row ─────────────────────────────────────────────────────────────────

function BuildRow({ entry }: { entry: BuildHistoryEntry }) {
  return (
    <li className="flex items-center gap-2">
      <Link
        href={`/build/${entry.hash}?s=${entry.encoded}`}
        className="canvas-card flex flex-1 items-center justify-between gap-3 border border-[var(--border-1)] p-3 transition-colors hover:border-[var(--border-2)]"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] text-[var(--fg-1)]">{entry.label}</span>
          <span className="block truncate font-mono text-[11px] text-[var(--fg-3)]">
            {entry.conceptSlug}
            {" · "}
            <span className="tam-num text-[11px]">{entry.hash.slice(0, 10)}</span>
          </span>
        </span>
        <span className="shrink-0 text-[11px] text-[var(--fg-3)]">
          {relativeTime(entry.visitedAt)}
        </span>
      </Link>
      <FavoriteStar entry={entry} />
    </li>
  );
}

// ── Favorites list ────────────────────────────────────────────────────────────

function FavoritesList() {
  const mounted = useHasMounted();
  const items = useFavoritesStore((s) => s.items);
  // localStorage is synchronous; once mounted the store is already populated.
  // No skeleton needed — either there are favorites or the section is absent.
  const favorites = mounted ? Object.values(items).sort((a, b) => b.visitedAt - a.visitedAt) : [];

  if (!mounted || favorites.length === 0) return null;

  return (
    <section aria-labelledby="bank-favorites-heading">
      <SectionLabel id="bank-favorites-heading">Favorites</SectionLabel>
      <ul className="flex flex-col gap-2">
        {favorites.map((e) => (
          <BuildRow key={e.hash} entry={e} />
        ))}
      </ul>
    </section>
  );
}

// ── Saved builds list ─────────────────────────────────────────────────────────

function SavedBuildsList() {
  const [entries, setEntries] = useState<BuildHistoryEntry[]>([]);
  const mounted = useHasMounted();

  useEffect(() => {
    setEntries(readBuildHistory());
  }, []);

  return (
    <section aria-labelledby="bank-builds-heading">
      <SectionLabel id="bank-builds-heading">Recent builds</SectionLabel>
      {!mounted ? (
        <div className="flex flex-col gap-2">
          {["a", "b", "c"].map((k) => (
            <Skeleton key={k} className="h-[52px] w-full" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="canvas-card border border-[var(--border-1)] p-5">
          <p className="text-[13px] text-[var(--fg-2)]">No builds yet.</p>
          <p className="mt-1 text-[12px] text-[var(--fg-3)]">
            Size a market from the{" "}
            <Link href="/" className="text-[var(--accent)] underline-offset-2 hover:underline">
              home page
            </Link>{" "}
            and it will appear here.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((e) => (
            <BuildRow key={e.hash} entry={e} />
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Gated builds (Clerk) ──────────────────────────────────────────────────────

function GatedBuilds() {
  if (!clerkEnabled) return <SavedBuildsList />;
  return (
    <>
      <Show when="signed-in">
        <SavedBuildsList />
      </Show>
      <Show when="signed-out">
        <section aria-labelledby="bank-builds-heading">
          <SectionLabel id="bank-builds-heading">Recent builds</SectionLabel>
          <div className="canvas-card flex flex-col items-start gap-3 border border-[var(--border-1)] p-5">
            <p className="text-[13px] text-[var(--fg-2)]">
              Sign in to see the TAM builds you have opened.
            </p>
            <SignInButton mode="modal">
              <button
                type="button"
                className="grid h-8 place-items-center rounded-[var(--r-2)] bg-[var(--accent)] px-3 text-[13px] font-medium text-[var(--accent-fg-on)] transition-colors hover:bg-[var(--accent-hover)] focus-visible:outline-none"
              >
                Sign in
              </button>
            </SignInButton>
          </div>
        </section>
      </Show>
    </>
  );
}

// ── Export ────────────────────────────────────────────────────────────────────

export function SavedBuildsSection() {
  return (
    <>
      <FavoritesList />
      <GatedBuilds />
    </>
  );
}

// ── Internal ──────────────────────────────────────────────────────────────────

function SectionLabel({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="mb-3 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]"
    >
      {children}
    </h2>
  );
}
