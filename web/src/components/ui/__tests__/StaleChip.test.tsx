/** Wave 1 / AC1.7 — StaleChip renders only past the freshness SLA. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { isStale, StaleChip } from "../StaleChip";

const NOW = new Date("2026-01-01T00:00:00Z");

describe("isStale", () => {
	it("is false with no SLA, false within SLA, true past SLA", () => {
		expect(isStale("2020-01-01", null, NOW)).toBe(false);
		expect(isStale("2025-12-01", 365, NOW)).toBe(false);
		expect(isStale("2024-01-01", 365, NOW)).toBe(true);
	});
});

describe("StaleChip", () => {
	it("renders nothing when fresh", () => {
		render(<StaleChip asOf="2025-12-01" freshnessSlaDays={365} now={NOW} />);
		expect(screen.queryByTestId("stale-chip")).toBeNull();
	});

	it("renders the chip when stale", () => {
		render(<StaleChip asOf="2024-01-01" freshnessSlaDays={365} now={NOW} />);
		expect(screen.getByTestId("stale-chip")).toHaveTextContent(/stale/i);
	});
});
