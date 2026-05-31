// Wave 1 / AC1.7 — a `stale` chip for a primitive whose data period (as_of) is
// older than its source's freshness SLA. Pure `isStale` so the rule is testable
// and identical to the backend (strata.staleness.is_stale).
const DAY_MS = 86_400_000;

export function isStale(
	asOf: string,
	freshnessSlaDays: number | null | undefined,
	now: Date = new Date(),
): boolean {
	if (freshnessSlaDays == null) return false;
	const asOfMs = Date.parse(asOf);
	if (Number.isNaN(asOfMs)) return false;
	const ageDays = Math.floor((now.getTime() - asOfMs) / DAY_MS);
	return ageDays > freshnessSlaDays;
}

export function StaleChip({
	asOf,
	freshnessSlaDays,
	now,
}: {
	asOf: string;
	freshnessSlaDays: number | null | undefined;
	now?: Date;
}) {
	if (!isStale(asOf, freshnessSlaDays, now)) return null;
	return (
		<span
			data-testid="stale-chip"
			title={`Data period ${asOf} is past its ${freshnessSlaDays}-day freshness window`}
			className="inline-flex items-center gap-1 rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--fg-3)]"
		>
			<span className="h-1.5 w-1.5 rounded-full bg-[var(--warning,#d97849)]" />
			stale
		</span>
	);
}
