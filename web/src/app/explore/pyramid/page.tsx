import { Suspense } from "react";

// Pyramid tab under /explore. GraphView renders the full interactive pyramid.
// `embedded` drops its own <main> + "Explore the pyramid" heading so it nests
// cleanly under /explore/layout.tsx (which already provides the <main> and the
// "Explore the Strata bank" heading) — no duplicate landmark, no double headline.
import { GraphView } from "@/app/graph/GraphView";

export default function ExplorePyramidPage() {
  return (
    <Suspense fallback={<PyramidSkeleton />}>
      <GraphView embedded />
    </Suspense>
  );
}

function PyramidSkeleton() {
  return (
    <div className="flex flex-1 items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </div>
  );
}
