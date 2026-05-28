import { Skeleton } from "@/components/ui/Skeleton";

// Route-level fallback while the /f segment streams.
export default function FrameworksLoading() {
  return (
    <main className="flex-1 flex flex-col">
      <div className="w-full px-8 py-5 border-b border-[var(--border-1)]">
        <Skeleton className="h-6 w-40" />
      </div>
      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
            <Skeleton key={i} className="h-[140px]" />
          ))}
        </div>
      </div>
    </main>
  );
}
