// Typed fetch wrapper. `gen:api` script generates `api-schema.d.ts` from
// the running FastAPI's /openapi.json. Until then, types fall back to
// `unknown` and the caller asserts a Zod shape.
import { env } from "./env";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Auth token accessor (Clerk → backend Bearer bridge, PR 1 / U9) ──────────────
//
// `api()` runs in BOTH the browser (react-query) and on the server (tam-server.ts
// during SSR). Clerk's `getToken()` is a client hook, so a Clerk-aware client
// component (`auth-bridge.tsx`) REGISTERS the accessor here once on mount. When no
// accessor is registered (server render, signed-out, or Clerk disabled) we send NO
// Authorization header — keyless/anonymous reads must keep working byte-identically
// to before (KTD-3/KTD-4: a missing Bearer falls through to the anonymous path).
type TokenGetter = () => Promise<string | null>;

let tokenGetter: TokenGetter | null = null;

export function setAuthTokenGetter(getter: TokenGetter | null): void {
  tokenGetter = getter;
}

async function resolveAuthHeader(): Promise<Record<string, string>> {
  if (!tokenGetter) return {};
  try {
    const token = await tokenGetter();
    return token ? { authorization: `Bearer ${token}` } : {};
  } catch {
    // A token fetch failure must never block a read — degrade to anonymous.
    return {};
  }
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const authHeader = await resolveAuthHeader();
  const res = await fetch(`${env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...authHeader,
      ...init.headers,
    },
  });

  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // Non-JSON response (e.g. HTML error page from proxy)
  }

  if (!res.ok) {
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
  }
  return body as T;
}
