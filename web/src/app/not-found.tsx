// App-level 404. Renders inside the persistent shell, so it keeps the sidebar
// + top bar — a missing page is a dead end with a way back, not a blank slate.
// Editorial and restrained, in the house style: serif headline, mono code motif,
// real navigational paths (never a link to "#").
import Link from "next/link";

import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col items-start justify-center gap-6 px-8 py-24">
      <div className="flex items-baseline gap-3">
        <span className="tam-num text-[64px] leading-none text-[var(--accent)]">404</span>
        <code className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-2 py-1 font-mono text-[12px] text-[var(--fg-3)]">
          no such hash
        </code>
      </div>

      <div className="flex flex-col gap-2">
        <h1 className="display text-[32px] leading-[1.1] text-[var(--fg-1)]">
          This page isn&rsquo;t in the ledger.
        </h1>
        <p className="max-w-[52ch] text-[14px] leading-relaxed text-[var(--fg-2)]">
          The link may be stale, or the TAM was never minted. Every sized market lives at a
          permanent <code className="font-mono text-[13px]">/tam/&lt;hash&gt;</code> — head back to
          a surface that exists.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Link href="/">
          <Button>Back to home</Button>
        </Link>
        <Link href="/browse">
          <Button variant="ghost">Browse TAMs</Button>
        </Link>
        <Link href="/connectors">
          <Button variant="ghost">Connectors</Button>
        </Link>
      </div>
    </main>
  );
}
