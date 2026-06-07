"use client";

// /oauth/authorize is the Clerk-gated OAuth consent surface. Like /build, it is
// entirely client-side: it reads the OAuth params off the query string and needs
// a live Clerk session, so SSR-ing it only triggers a useSearchParams CSR-bailout
// whose Suspense fallback fails to reconcile. Render ConsentView client-only
// (ssr:false) so the server emits the placeholder and the client mounts the view.
import dynamic from "next/dynamic";

const ConsentView = dynamic(() => import("./ConsentView").then((m) => m.ConsentView), {
  ssr: false,
  loading: () => (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  ),
});

export default function OAuthAuthorizePage() {
  return <ConsentView />;
}
