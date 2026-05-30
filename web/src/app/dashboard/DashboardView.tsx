"use client";

// The /dashboard client view. Three panels:
//   1. Library counts   — reuses the sidebar's live concept/primitive/framework
//                          queries (public).
//   2. Your builds      — the local state-hash history (per-browser, gated behind
//                          sign-in when Clerk is configured).
//   3. Audit feed       — GET /audit, newest-first (public).
//
// Auth degrades gracefully: with no Clerk keys the page shows a clear notice and
// the public panels, never a crash.
import { Show, SignInButton } from "@clerk/nextjs";
import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/Skeleton";
import { type BuildHistoryEntry, readBuildHistory } from "@/lib/build-history";
import { clerkEnabled } from "@/lib/clerk";
import { auditQuery, conceptsQuery, frameworksQuery, primitivesQuery } from "@/lib/queries";
import type { AuditEvent } from "@/lib/schemas";

const nf = new Intl.NumberFormat("en-US");

export function DashboardView() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max,1100px)] flex-1 flex-col gap-8 px-8 py-8">
      <header>
        <h1 className="display text-[28px] text-[var(--fg-1)]">Dashboard</h1>
        <p className="mt-1 text-[13px] text-[var(--fg-3)]">
          Your saved builds, the live library, and the platform audit trail.
        </p>
      </header>

      {!clerkEnabled && <AuthNotice />}

      <LibraryCounts />

      <SavedBuilds />

      <AuditFeed />
    </main>
  );
}

// ── Auth notice (Clerk not configured) ───────────────────────────────────────
function AuthNotice() {
  return (
    <div className="canvas-card border border-[var(--border-2)] p-4">
      <p className="text-[13px] font-medium text-[var(--fg-1)]">Authentication not configured</p>
      <p className="mt-1 text-[12px] leading-relaxed text-[var(--fg-3)]">
        Set <code className="font-mono text-[var(--fg-2)]">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>{" "}
        + <code className="font-mono text-[var(--fg-2)]">CLERK_SECRET_KEY</code> to enable sign-in
        and per-user build history. The public panels below work without it.
      </p>
    </div>
  );
}

// ── Library counts ───────────────────────────────────────────────────────────
function LibraryCounts() {
  const [concepts, primitives, frameworks] = useQueries({
    queries: [conceptsQuery, primitivesQuery, frameworksQuery],
  });

  return (
    <section>
      <SectionLabel>Library</SectionLabel>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <CountCard
          label="Concepts"
          href="/c"
          value={concepts.data?.length}
          pending={concepts.isPending}
        />
        <CountCard
          label="Primitives"
          href="/p"
          value={primitives.data?.length}
          pending={primitives.isPending}
        />
        <CountCard
          label="Frameworks"
          href="/f"
          value={frameworks.data?.length}
          pending={frameworks.isPending}
        />
      </div>
    </section>
  );
}

function CountCard({
  label,
  href,
  value,
  pending,
}: {
  label: string;
  href: string;
  value: number | undefined;
  pending: boolean;
}) {
  return (
    <Link
      href={href}
      className="canvas-card flex flex-col gap-1 p-4 transition-colors hover:border-[var(--border-3)]"
    >
      <span className="text-[12px] uppercase tracking-[0.06em] text-[var(--fg-3)]">{label}</span>
      {pending ? (
        <Skeleton className="h-8 w-16" />
      ) : (
        <span className="tam-num text-[26px] text-[var(--fg-1)]">
          {value === undefined ? "—" : nf.format(value)}
        </span>
      )}
    </Link>
  );
}

// ── Saved builds (local state-hash history) ──────────────────────────────────
function SavedBuilds() {
  // Gate behind sign-in when Clerk is on; otherwise show directly (no auth layer).
  if (!clerkEnabled) return <SavedBuildsList />;
  return (
    <>
      <Show when="signed-in">
        <SavedBuildsList />
      </Show>
      <Show when="signed-out">
        <section>
          <SectionLabel>Your builds</SectionLabel>
          <div className="canvas-card flex flex-col items-start gap-2 p-4">
            <p className="text-[13px] text-[var(--fg-2)]">
              Sign in to see the TAM builds you've opened.
            </p>
            <SignInButton mode="modal">
              <button
                type="button"
                className="grid h-8 place-items-center rounded-[var(--r-2)] bg-[var(--accent)] px-3 text-[13px] font-medium text-[var(--accent-fg-on)] transition-colors hover:bg-[var(--accent-hover)]"
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

function SavedBuildsList() {
  // localStorage is browser-only; read after mount so the server and first client
  // render agree (empty), then fill in.
  const [entries, setEntries] = useState<BuildHistoryEntry[]>([]);
  useEffect(() => {
    setEntries(readBuildHistory());
  }, []);

  return (
    <section>
      <SectionLabel>Your builds</SectionLabel>
      {entries.length === 0 ? (
        <div className="canvas-card p-4 text-[13px] text-[var(--fg-3)]">
          No saved builds yet. Size a market from the{" "}
          <Link href="/" className="text-[var(--accent)] hover:underline">
            home page
          </Link>{" "}
          and it will appear here.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((e) => (
            <li key={e.hash}>
              <Link
                href={`/build/${e.hash}?s=${e.encoded}`}
                className="canvas-card flex items-center justify-between gap-3 p-3 transition-colors hover:border-[var(--border-3)]"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] text-[var(--fg-1)]">{e.label}</span>
                  <span className="block truncate font-mono text-[11px] text-[var(--fg-3)]">
                    {e.conceptSlug} · {e.hash.slice(0, 10)}
                  </span>
                </span>
                <span className="shrink-0 text-[11px] text-[var(--fg-3)]">
                  {relativeTime(e.visitedAt)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Audit feed ───────────────────────────────────────────────────────────────
function AuditFeed() {
  const audit = useQuery(auditQuery(50, 0));

  return (
    <section>
      <SectionLabel>Audit feed</SectionLabel>
      {audit.isPending ? (
        <div className="flex flex-col gap-2">
          {["a", "b", "c", "d"].map((k) => (
            <Skeleton key={k} className="h-10 w-full" />
          ))}
        </div>
      ) : audit.error ? (
        <div className="canvas-card p-4 text-[13px] text-[var(--fg-3)]">
          Audit feed unavailable.
        </div>
      ) : audit.data && audit.data.length > 0 ? (
        <ul className="canvas-card divide-y divide-[var(--border-1)] overflow-hidden">
          {audit.data.map((ev) => (
            <AuditRow key={ev.id} ev={ev} />
          ))}
        </ul>
      ) : (
        <div className="canvas-card p-4 text-[13px] text-[var(--fg-3)]">No activity yet.</div>
      )}
    </section>
  );
}

function AuditRow({ ev }: { ev: AuditEvent }) {
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-[12px]">
      <span className="font-mono text-[var(--fg-2)]">{ev.actor ?? "anon"}</span>
      <span className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--fg-1)]">
        {ev.action}
      </span>
      {ev.target && <span className="truncate text-[var(--fg-3)]">{ev.target}</span>}
      <span className="ml-auto shrink-0 text-[var(--fg-3)]">{relativeTime(ev.ts)}</span>
    </li>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]">
      {children}
    </h2>
  );
}

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

// Compact "3h ago" style label from an epoch-ms number or an ISO timestamp.
function relativeTime(input: number | string): string {
  // A naive ISO timestamp (no Z / offset) is parsed as LOCAL time by Date.parse;
  // the audit `ts` is UTC, so append Z when no zone is present to avoid TZ drift.
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
