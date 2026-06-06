// Auto-mint workhorse route (U6 · design 18-build). The path segment is the
// state hash; ?s= carries the full BuildState so a reload/back/share round-trips
// losslessly (the backend does NOT persist computed TAMs — /tam/{hash} 404s — so
// the encoded state is the only recovery path). Next 16: params & searchParams
// are Promises in server components; we only unwrap them and hand the data to
// the client view, which owns the tanstack fetch, the rail, and auto-mint.
import { BuildHashView } from "@/components/build/BuildHashView";

type Props = {
  params: Promise<{ hash: string }>;
  searchParams: Promise<{ s?: string | string[]; mode?: string | string[] }>;
};

export default async function BuildHashPage({ params, searchParams }: Props) {
  const { hash } = await params;
  const { s, mode } = await searchParams;
  // ?s= is single-valued; if a duplicate key sneaks in, take the first.
  const encoded = Array.isArray(s) ? (s[0] ?? null) : (s ?? null);
  const m = Array.isArray(mode) ? mode[0] : mode;
  // ?mode=studio reproduces the Build Studio reveal at this hash (a steer from
  // inside the studio mints this URL); any other value renders the workhorse.
  return <BuildHashView hash={hash} s={encoded} studio={m === "studio"} />;
}
