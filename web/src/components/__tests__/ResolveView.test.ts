import { describe, expect, it } from "vitest";

import type { SSEEnvelope } from "@/lib/resolver-client";
import { type State, initialState, reducer } from "../ResolveView";

// Drive the reducer over a list of SSE envelopes, mirroring the stream loop.
function run(envelopes: SSEEnvelope[], start: State = initialState): State {
  return envelopes.reduce(
    (state, envelope) => reducer(state, { kind: "envelope", envelope }),
    start,
  );
}

// The authentic success-path wire sequence emitted by backend routes/resolve.py.
const SUCCESS: SSEEnvelope[] = [
  { event: "parsing", data: { query: "doc gen", model: "claude-sonnet-4-6" } },
  {
    event: "step",
    data: { type: "parsing", message: 'Parsing: "doc gen"...' },
  },
  {
    event: "searching",
    data: { primitive_name: "persona_pool", role: "persona_pool" },
  },
  {
    event: "step",
    data: {
      type: "primitive_found",
      role: "persona_pool",
      name: "Claims adjusters headcount",
      value: 322500,
      source_url: "https://bls.gov",
      source_tier: "regulator",
    },
  },
  {
    event: "framework_selected",
    data: { framework: "cost_efficiency", lens: "cost_efficiency" },
  },
  {
    event: "step",
    data: {
      type: "framework_selected",
      name: "Bottoms-up cost efficiency",
      lens: "cost_efficiency",
    },
  },
  { event: "evaluating", data: { inputs: [] } },
  {
    event: "step",
    data: { type: "evaluating", message: "Computing TAM scenarios..." },
  },
  {
    event: "result",
    data: {
      tam_usd: 5_000_000_000,
      scenarios: [{ label: "point", value: 5_000_000_000 }],
      sources: [{ url: "https://bls.gov", tier: "regulator" }],
      concept_name: "P&C doc gen",
      tam_value: 5_000_000_000,
      formatted_tam: "$5.00B",
      lens: "cost_efficiency",
      framework_name: "Bottoms-up cost efficiency",
      independence_score: 0.5,
      primitives_used: [
        {
          role: "persona_pool",
          name: "Claims adjusters headcount",
          value: 322500,
          source_url: "https://bls.gov",
          source_tier: "regulator",
        },
      ],
      banner: null,
    },
  },
  { event: "done", data: {} },
];

describe("ResolveView reducer", () => {
  it("folds the frozen event sequence into ordered chain-of-thought rows", () => {
    const state = run(SUCCESS);
    expect(state.rows.map((r) => r.phase)).toEqual([
      "parsing",
      "searching",
      "framework_selected",
      "evaluating",
    ]);
    expect(state.status).toBe("done");
  });

  it("attaches a primitive_found step to the searching row as a hit", () => {
    const state = run(SUCCESS);
    const searching = state.rows.find((r) => r.phase === "searching");
    expect(searching?.hits).toHaveLength(1);
    expect(searching?.hits[0]).toMatchObject({
      name: "Claims adjusters headcount",
      value: 322500,
      source_tier: "regulator",
    });
  });

  it("records the framework name from the step envelope", () => {
    const state = run(SUCCESS);
    const fw = state.rows.find((r) => r.phase === "framework_selected");
    expect(fw?.framework).toBe("Bottoms-up cost efficiency");
  });

  it("validates the result payload with resolverResultSchema and keeps primitives", () => {
    const state = run(SUCCESS);
    expect(state.result).not.toBeNull();
    expect(state.result?.formatted_tam).toBe("$5.00B");
    expect(state.result?.independence_score).toBe(0.5);
    expect(state.result?.primitives_used).toHaveLength(1);
  });

  it("does not create a duplicate row when a phase repeats", () => {
    const state = run([...SUCCESS, ...SUCCESS]);
    const searchingRows = state.rows.filter((r) => r.phase === "searching");
    expect(searchingRows).toHaveLength(1);
    // The repeat run appends another hit to the same row.
    expect(searchingRows[0].hits.length).toBeGreaterThanOrEqual(1);
  });

  it("captures an error envelope as a terminal error state", () => {
    const state = run([
      { event: "parsing", data: { query: "x", model: "m" } },
      {
        event: "error",
        data: { message: "Failed to parse AI response.", step: "search" },
      },
      { event: "done", data: {} },
    ]);
    expect(state.status).toBe("error");
    expect(state.error).toBe("Failed to parse AI response.");
  });

  it("surfaces an unreadable result as an error rather than crashing", () => {
    const state = run([{ event: "result", data: { independence_score: "not-a-number" } }]);
    expect(state.status).toBe("error");
    expect(state.error).toMatch(/unreadable/i);
  });
});
