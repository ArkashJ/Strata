import type { Unit } from "./schemas";

// Build-view state canonicalization + content-addressing.
//
// Every meaningful state change on /build mints a /build/<state-hash> URL (U5).
// Equivalent states must collide, so we canonicalize (sort keys, drop nullish)
// before hashing. The hash is SHA-256 hex via Web Crypto; the encoded form is
// base64url JSON so the full state survives a round-trip through the URL.

// A transient what-if scalar override on a primitive. URL-only: it is never
// written back to the registry as a citable primitive (Q20). The backend flags
// every scenario it touches with a `user_override` banner + uses_synthetic.
export interface PrimitiveOverride {
  value: number;
  // structured Unit (kind/dimension/...); the backend validates it against the
  // consuming framework input's unit_signature before recomputing.
  unit: Unit;
}

export interface BuildState {
  target_concept_slug: string;
  geo?: string | null;
  time?: string | null;
  expansion_stage?: string | null;
  frameworks_selected: string[];
  // framework slug → (input role name → primitive slug)
  framework_assumptions: Record<string, Record<string, string>>;
  // input role / slot → pinned primitive slug
  primitive_pins: Record<string, string>;
  // primitive slug → transient what-if scalar override (not sourced)
  primitive_overrides: Record<string, PrimitiveOverride>;
}

// Recursively sort object keys so logically-equal states serialize identically.
// Arrays preserve order (frameworks_selected ordering is meaningful to the UI)
// except where the caller has already normalized them.
function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      out[key] = sortValue((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  return value;
}

// Canonical JSON string. Order-independent: any two states that differ only in
// key insertion order (or in selected-framework ordering) produce one string.
export function canonicalizeState(state: BuildState): string {
  const normalized: BuildState = {
    target_concept_slug: state.target_concept_slug,
    geo: state.geo ?? null,
    time: state.time ?? null,
    expansion_stage: state.expansion_stage ?? null,
    // sort so [a, b] and [b, a] collide — selection is a set, not a sequence
    frameworks_selected: [...state.frameworks_selected].sort(),
    framework_assumptions: state.framework_assumptions ?? {},
    primitive_pins: state.primitive_pins ?? {},
    primitive_overrides: state.primitive_overrides ?? {},
  };
  return JSON.stringify(sortValue(normalized));
}

const encoder = new TextEncoder();

function toHex(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let hex = "";
  for (const byte of bytes) {
    hex += byte.toString(16).padStart(2, "0");
  }
  return hex;
}

// SHA-256 hex of the canonical state. 64 lowercase hex chars.
export async function hashState(state: BuildState): Promise<string> {
  const canonical = canonicalizeState(state);
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(canonical));
  return toHex(digest);
}

function base64UrlEncode(input: string): string {
  // btoa expects a binary string; encode UTF-8 bytes as Latin-1 first so
  // multi-byte characters survive the round-trip.
  const utf8 = encoder.encode(input);
  let binary = "";
  for (const byte of utf8) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new TextDecoder().decode(bytes);
}

// URL-safe encoding of the full state — lets /build links carry their state
// inline (the hash addresses it, this transports it). Encodes the canonical
// form so encode(s) is stable across equivalent states.
export function encodeState(state: BuildState): string {
  return base64UrlEncode(canonicalizeState(state));
}

export function decodeState(encoded: string): BuildState {
  return JSON.parse(base64UrlDecode(encoded)) as BuildState;
}
