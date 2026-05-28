import { Skeleton } from "@/components/ui/Skeleton";

// Route-level fallback while the concepts registry streams.
export default function BrowseLoading() {
  return (
    <main className="flex flex-1 flex-col">
      <div className="w-full border-b border-[var(--border-1)] px-8 py-5">
        <Skeleton className="h-6 w-40" />
      </div>
      <div className="mx-auto w-full max-w-[1280px] flex-1 px-8 py-8">
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
