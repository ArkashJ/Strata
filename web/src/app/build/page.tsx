import { Suspense } from "react";

import { BuildView } from "./BuildView";

export default function BuildPage() {
  return (
    <Suspense fallback={<BuildSkeleton />}>
      <BuildView />
    </Suspense>
  );
}

function BuildSkeleton() {
  return (
    <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
      Loading…
    </main>
  );
}
