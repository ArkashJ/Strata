// App-level 404. The web app is retired (CLI + MCP are the product), so any
// old app route lands here — editorial and restrained, with a way back to the
// one surviving surface.
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
          The web app has been retired — Strata now ships through the CLI and the MCP server. The
          link may point to a page that no longer exists here.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Link href="/">
          <Button>Back to home</Button>
        </Link>
      </div>
    </main>
  );
}
