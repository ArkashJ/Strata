"use client";

// Dashboard route. Rendered client-only: it reads localStorage build history,
// live library counts (TanStack), and the audit feed — none of which need a
// server render, and SSR-ing the localStorage read would only cause a hydration
// mismatch. Next 16 forbids `ssr:false` dynamic() in a Server Component, so this
// page is a Client Component (same pattern as /build/page.tsx). The auth gate
// degrades gracefully when Clerk is unconfigured (prod).
import dynamic from "next/dynamic";

const DashboardView = dynamic(() => import("./DashboardView").then((m) => m.DashboardView), {
  ssr: false,
  loading: () => (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  ),
});

export default function DashboardPage() {
  return <DashboardView />;
}
