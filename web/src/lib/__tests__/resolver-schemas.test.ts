import { describe, expect, it } from "vitest";

import { isFrozenSSEEvent, isKnownSSEEvent, parseSSEBuffer } from "../resolver-client";
import {
  FROZEN_SSE_EVENTS,
  capabilitySpecSchema,
  pipelineEventKindSchema,
  pipelineEventSchema,
  resolvedQuerySchema,
  resolverResultSchema,
  routingDecisionSchema,
} from "../resolver-schemas";

describe("resolver-schemas (frontend ↔ backend contract)", () => {
  it("includes every §9.1 frozen event in PipelineEventKind", () => {
    for (const name of FROZEN_SSE_EVENTS) {
      const result = pipelineEventKindSchema.safeParse(name);
      expect(result.success).toBe(true);
    }
  });

  it("validates a minimal ResolvedQuery", () => {
    const out = resolvedQuerySchema.parse({
      intent: "concept",
      concept_slug: "us-pc-doc-gen",
      primitive_slugs: [],
      framework_hint: null,
      confidence: 0.92,
    });
    expect(out.intent).toBe("concept");
  });

  it("rejects ResolvedQuery with out-of-range confidence", () => {
    const result = resolvedQuerySchema.safeParse({
      intent: "novel",
      primitive_slugs: [],
      confidence: 1.5,
    });
    expect(result.success).toBe(false);
  });

  it("accepts a populated ResolverResult", () => {
    const out = resolverResultSchema.parse({
      status: "ok",
      via: "connector",
      tam_value: 1_234.0,
      formatted_tam: "$1.2K",
      primitives_used: [
        {
          slug: "fdic-deposits-us-2024",
          value: 100,
          unit: { kind: "stock", dimension: "currency" },
        },
      ],
      wrote_primitives: ["fdic-deposits-us-2024"],
      events: [],
    });
    expect(out.status).toBe("ok");
    expect(out.via).toBe("connector");
  });

  it("validates RoutingDecision", () => {
    const out = routingDecisionSchema.parse({
      connector: "fdic",
      method: "get_total_deposits",
      args: { report_date: "20241231" },
      confidence: 0.94,
      rationale: "FDIC tier=regulator, exact match for US bank deposits",
    });
    expect(out.connector).toBe("fdic");
    expect(out.confidence).toBe(0.94);
  });

  it("validates CapabilitySpec with both fragile + paid flags", () => {
    const out = capabilitySpecSchema.parse({
      connector: "alpha_vantage",
      method: "get_company_overview",
      description: "Company fundamentals",
      returns: "atomic primitive",
      args: [{ name: "symbol", type: "str", description: "Ticker", example: "AAPL" }],
      source_tier: "aggregator",
      is_fragile: true,
      requires_paid_tier: false,
    });
    expect(out.is_fragile).toBe(true);
  });

  it("PipelineEvent.step is constrained to the 5 known values", () => {
    expect(
      pipelineEventSchema.safeParse({ kind: "parsing", step: "pre", payload: {} }).success,
    ).toBe(true);
    expect(pipelineEventSchema.safeParse({ kind: "parsing", step: "5", payload: {} }).success).toBe(
      false,
    );
  });
});

describe("resolver-client SSE parsing", () => {
  it("isFrozenSSEEvent / isKnownSSEEvent reflect the §9.1 set", () => {
    expect(isFrozenSSEEvent("parsing")).toBe(true);
    expect(isFrozenSSEEvent("done")).toBe(false);
    expect(isKnownSSEEvent("done")).toBe(true); // legacy
    expect(isKnownSSEEvent("not-a-thing")).toBe(false);
  });

  it("parseSSEBuffer collects complete blocks and returns the partial rest", () => {
    const input =
      'event: parsing\ndata: {"query":"x"}\n\n' +
      'event: searching\ndata: {"role":"a"}\n\n' +
      "event: par"; // incomplete

    const { envelopes, rest } = parseSSEBuffer(input);
    expect(envelopes).toHaveLength(2);
    expect(envelopes[0].event).toBe("parsing");
    expect(envelopes[1].event).toBe("searching");
    expect(rest.startsWith("event: par")).toBe(true);
  });

  it("parseSSEBuffer passes through non-JSON data", () => {
    const input = "event: heartbeat\ndata: keep-alive\n\n";
    const { envelopes } = parseSSEBuffer(input);
    expect(envelopes).toHaveLength(1);
    expect(envelopes[0].data).toBe("keep-alive");
  });
});
