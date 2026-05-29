// Route-level fallback while the server component resolves params. The client
// view shows its own query skeleton once mounted; this covers the gap before.
import { Skeleton } from "@/components/ui/Skeleton";

export default function TamLoading() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-6 px-8 py-8">
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-12 w-2/3" />
      <Skeleton className="h-8 w-96" />
      <Skeleton className="h-[220px] w-full" />
      <Skeleton className="h-[420px] w-full" />
    </main>
  );
}
