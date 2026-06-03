// Shared shell for the Clerk auth routes: the night canvas, the brand header
// with a cross-link to the sibling auth page, and the glass card the Clerk
// component renders into. Sign-in and sign-up were byte-identical apart from
// the embedded component and the cross-link — restyle the auth chrome here,
// once.
import Link from "next/link";

import { NightCanvas } from "@/components/landing/NightCanvas";
import { Logo } from "@/components/shell/Logo";

export function AuthCanvas({
  altHref,
  altLabel,
  children,
}: {
  altHref: string;
  altLabel: string;
  children: React.ReactNode;
}) {
  return (
    <NightCanvas>
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <Link href="/" className="flex items-center gap-2.5">
          <Logo />
          <span className="display text-[18px] italic leading-none text-[var(--night-fg-1)]">
            Strata
          </span>
        </Link>
        <Link
          href={altHref}
          className="text-[13px] text-[var(--night-fg-2)] transition-colors hover:text-[var(--night-fg-1)]"
        >
          {altLabel}
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="glass w-full max-w-[420px] p-7 sm:p-9">{children}</div>
      </main>
    </NightCanvas>
  );
}
