import { Skeleton } from "@/components/ui/Skeleton";

// Route-level fallback while the concepts list (or any /c segment) streams.
export default function ConceptsLoading() {
  return (
    <main className="flex-1 flex flex-col">
      <div className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <Skeleton className="h-6 w-40" />
      </div>
      <div className="flex-1 px-8 py-8 max-w-[1280px] mx-auto w-full">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }, (_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
            <Skeleton key={i} className="h-[148px]" />
          ))}
        </div>
      </div>
    </main>
  );
}
