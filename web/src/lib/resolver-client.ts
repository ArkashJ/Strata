/**
 * Streaming client for `POST /resolve`.
 *
 * The route emits Server-Sent Events with the §9.1 frozen set plus
 * the legacy `step` / `done` envelopes. This wrapper exposes an async
 * generator yielding {event, data} pairs so callers can render the
 * pipeline trace incrementally (see ResolveView.tsx).
 */

import { env } from "./env";
import { FROZEN_SSE_EVENTS, LEGACY_SSE_EVENTS, type PipelineEventKind } from "./resolver-schemas";

export type SSEEnvelope = {
  event: string;
  data: unknown;
};

export type ResolveRequestBody = {
  query: string;
};

export class ResolverStreamError extends Error {
  constructor(
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "ResolverStreamError";
  }
}

const KNOWN_EVENTS = new Set<string>([...FROZEN_SSE_EVENTS, ...LEGACY_SSE_EVENTS]);

export function isFrozenSSEEvent(name: string): name is PipelineEventKind {
  return (FROZEN_SSE_EVENTS as readonly string[]).includes(name);
}

export function isLegacySSEEvent(name: string): name is (typeof LEGACY_SSE_EVENTS)[number] {
  return (LEGACY_SSE_EVENTS as readonly string[]).includes(name);
}

export function isKnownSSEEvent(name: string): boolean {
  return KNOWN_EVENTS.has(name);
}

/**
 * Parse a chunk-buffered raw SSE body into envelope tokens.
 * Used by the streamResolve generator; exported for unit tests.
 */
export function parseSSEBuffer(buffer: string): { envelopes: SSEEnvelope[]; rest: string } {
  const envelopes: SSEEnvelope[] = [];
  const blocks = buffer.split("\n\n");
  // The last block may be incomplete — preserve it as "rest" for the next chunk.
  const rest = blocks.pop() ?? "";

  for (const block of blocks) {
    let event = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice("event:".length).trim();
      else if (line.startsWith("data:")) data += line.slice("data:".length).trim();
    }
    if (!event) continue;
    let parsed: unknown = data;
    try {
      parsed = data ? JSON.parse(data) : null;
    } catch {
      // Non-JSON data — pass through as a string.
    }
    envelopes.push({ event, data: parsed });
  }

  return { envelopes, rest };
}

/**
 * Async generator yielding {event, data} as the stream arrives.
 *
 * Caller is expected to break out of the for-await loop when an
 * envelope with `event === "done"` arrives. AbortSignal is supported.
 */
export async function* streamResolve(
  body: ResolveRequestBody,
  init: { signal?: AbortSignal } = {},
): AsyncGenerator<SSEEnvelope, void, void> {
  const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/resolve`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: init.signal,
  });

  if (!response.ok || !response.body) {
    throw new ResolverStreamError(
      `Resolver stream failed: ${response.status} ${response.statusText}`,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { envelopes, rest } = parseSSEBuffer(buffer);
      buffer = rest;
      for (const envelope of envelopes) {
        yield envelope;
        if (envelope.event === "done") return;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
