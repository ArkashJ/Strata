import { Skeleton } from "@/components/ui/Skeleton";

// Route-level fallback while the /p segment streams.
export default function PrimitivesLoading() {
  return (
    <main className="flex-1 flex flex-col">
      <div className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <Skeleton className="h-6 w-40" />
      </div>
      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full flex flex-col gap-1">
        {Array.from({ length: 12 }, (_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
          <Skeleton key={i} className="h-11 w-full" />
        ))}
      </div>
    </main>
  );
}
