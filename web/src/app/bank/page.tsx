"use client";

// My Bank — the user's personal data tier.
//
// Rendered client-only for the same reason as /dashboard: localStorage build
// history + Zustand favorites are browser-only, and SSR-ing them causes
// hydration mismatches. Next 16 forbids ssr:false dynamic() in Server
// Components, so this page is a Client Component.
//
// Three panels, in reading order:
//   1. My primitives  — private server store, GET /me/primitives (myPrimitivesQuery)
//   2. Saved builds   — saved research (GET /me/tams) + local favorites/history
//   3. Activity       — per-user audit feed, GET /me/audit (myAuditQuery)
import dynamic from "next/dynamic";

const BankView = dynamic(() => import("./BankView").then((m) => m.BankView), {
  ssr: false,
  loading: () => (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  ),
});

export default function BankPage() {
  return <BankView />;
}
