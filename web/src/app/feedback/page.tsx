"use client";

// Feedback — the assumption-flagging triage queue (Phase F).
//
// Rendered client-only: the list is auth-gated (GET /feedback is org-scoped via
// the Clerk→Principal bridge, which only resolves in the browser), and the
// resolve action mutates. Next 16 forbids ssr:false dynamic() in a Server
// Component, so this page is a Client Component delegating to FeedbackView.
import dynamic from "next/dynamic";

const FeedbackView = dynamic(() => import("./FeedbackView").then((m) => m.FeedbackView), {
  ssr: false,
  loading: () => (
    <main className="flex flex-1 items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  ),
});

export default function FeedbackPage() {
  return <FeedbackView />;
}
