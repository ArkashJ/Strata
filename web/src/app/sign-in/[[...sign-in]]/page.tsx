// Clerk catch-all sign-in route, on the Strata night canvas (no app chrome).
// The [[...sign-in]] optional-catch-all lets Clerk own every sub-path
// (factor-two, SSO callback, etc.) under /sign-in.
import { SignIn } from "@clerk/nextjs";
import Link from "next/link";
import { redirect } from "next/navigation";

import { NightCanvas } from "@/components/landing/NightCanvas";
import { Logo } from "@/components/shell/Logo";
import { clerkEnabled } from "@/lib/clerk";
import { strataClerkAppearance } from "@/lib/clerk-appearance";

export default function SignInPage() {
  if (!clerkEnabled) redirect("/");
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
          href="/sign-up"
          className="text-[13px] text-[var(--night-fg-2)] transition-colors hover:text-[var(--night-fg-1)]"
        >
          Create account
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="glass w-full max-w-[420px] p-7 sm:p-9">
          <SignIn appearance={strataClerkAppearance} />
        </div>
      </main>
    </NightCanvas>
  );
}
