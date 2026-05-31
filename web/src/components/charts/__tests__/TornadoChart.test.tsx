/** Wave 2 / AC2.3 — tornado data is sorted by |impact| descending. */
import { describe, expect, it } from "vitest";

import { type SensitivityResponse, toTornadoData } from "../TornadoChart";

const RESP: SensitivityResponse = {
	concept_slug: "demo",
	base: 100,
	pct: 0.2,
	inputs: [
		{
			primitive_slug: "a",
			name: "small",
			base: 100,
			low: 95,
			high: 105,
			impact: 10,
		},
		{
			primitive_slug: "b",
			name: "big",
			base: 100,
			low: 60,
			high: 140,
			impact: 80,
		},
		{
			primitive_slug: "c",
			name: "mid",
			base: 100,
			low: 80,
			high: 120,
			impact: 40,
		},
	],
};

describe("toTornadoData", () => {
	it("sorts rows by |impact| descending", () => {
		const rows = toTornadoData(RESP);
		expect(rows.map((r) => r.slug)).toEqual(["b", "c", "a"]);
		expect(rows.map((r) => r.impact)).toEqual([80, 40, 10]);
	});

	it("normalises range to [min, max]", () => {
		const flipped: SensitivityResponse = {
			...RESP,
			inputs: [
				{
					primitive_slug: "z",
					name: "z",
					base: 100,
					low: 140,
					high: 60,
					impact: 80,
				},
			],
		};
		const [row] = toTornadoData(flipped);
		expect(row.range).toEqual([60, 140]);
	});
});
