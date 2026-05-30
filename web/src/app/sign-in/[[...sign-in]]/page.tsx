// Clerk catch-all sign-in route. The [[...sign-in]] optional-catch-all lets Clerk
// own every sub-path (factor-two, SSO callback, etc.) under /sign-in.
import { SignIn } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { clerkEnabled } from "@/lib/clerk";

export default function SignInPage() {
  // Without keys there is no ClerkProvider, so <SignIn/> would render a broken
  // shell — send the visitor home instead (matches the keyless-prod state).
  if (!clerkEnabled) redirect("/");
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <SignIn />
    </main>
  );
}
