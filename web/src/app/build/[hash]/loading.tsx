// Route-level fallback while the server component unwraps params/searchParams.
// The client view shows its own query skeleton once mounted; this covers the gap.
import { Skeleton } from "@/components/ui/Skeleton";

export default function BuildHashLoading() {
	return (
		<main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-6 px-8 py-8">
			<Skeleton className="h-4 w-48" />
			<Skeleton className="h-12 w-2/3" />
			<Skeleton className="h-5 w-64" />
			<Skeleton className="h-[140px] w-full" />
			<Skeleton className="h-[520px] w-full" />
		</main>
	);
}
