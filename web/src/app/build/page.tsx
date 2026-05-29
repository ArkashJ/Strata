"use client";

// /build?q=<query> is an entirely client-side surface: it reads the query string,
// runs client queries, then either redirects to /build/<hash> or streams a live
// resolution. There is no meaningful server render, and SSR-ing it only triggers
// a useSearchParams CSR-bailout whose Suspense fallback ("Loading…") then fails to
// reconcile against the client's <main> content. Rendering BuildView client-only
// (ssr:false) makes the server emit the placeholder and the client mount the real
// view — no hydration comparison, no mismatch.
import dynamic from "next/dynamic";

const BuildView = dynamic(() => import("./BuildView").then((m) => m.BuildView), {
  ssr: false,
  loading: () => (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  ),
});

export default function BuildPage() {
  return <BuildView />;
}
