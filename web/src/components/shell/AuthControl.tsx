"use client";

// Top-bar auth affordance. Renders nothing unless Clerk is configured, so the
// shell looks identical in the keyless prod deploy. When enabled: a compact
// "Sign in" button for signed-out users, the Clerk user avatar for signed-in.
import { Show, SignInButton, UserButton } from "@clerk/nextjs";

import { clerkEnabled } from "@/lib/clerk";

export function AuthControl() {
  if (!clerkEnabled) return null;
  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="modal">
          <button
            type="button"
            className="grid h-8 place-items-center rounded-[var(--r-2)] border border-[var(--border-2)] px-3 text-[13px] text-[var(--fg-1)] transition-colors hover:border-[var(--border-3)] hover:bg-[var(--bg-2)]"
          >
            Sign in
          </button>
        </SignInButton>
      </Show>
      <Show when="signed-in">
        <UserButton appearance={{ elements: { avatarBox: "h-7 w-7" } }} />
      </Show>
    </>
  );
}
