import { Suspense } from "react";

// Pyramid tab under /explore. The GraphView component renders the full
// interactive pyramid. It includes its own descriptive heading and filters,
// so no additional filter bar is needed here.
//
// NOTE for integrator: GraphView currently wraps its content in a <main>
// element. Since /explore/layout.tsx already provides the outer <main>,
// this creates nested <main> elements (invalid HTML). A follow-up should
// refactor GraphView to accept a `as` prop or extract its inner content
// into a `PyramidContent` component so the root element can be swapped.
// The functional behavior is correct in the meantime.
import { GraphView } from "@/app/graph/GraphView";

export default function ExplorePyramidPage() {
  return (
    <Suspense fallback={<PyramidSkeleton />}>
      <GraphView />
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
