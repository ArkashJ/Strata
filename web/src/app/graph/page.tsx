import { Suspense } from "react";

import { GraphView } from "./GraphView";

export default function GraphPage() {
  return (
    <Suspense fallback={<GraphSkeleton />}>
      <GraphView />
    </Suspense>
  );
}

function GraphSkeleton() {
  return (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  );
}
