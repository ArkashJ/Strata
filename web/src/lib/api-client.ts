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

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
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
