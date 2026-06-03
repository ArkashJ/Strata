// Clerk catch-all sign-in route, on the Strata night canvas (no app chrome).
// The [[...sign-in]] optional-catch-all lets Clerk own every sub-path
// (factor-two, SSO callback, etc.) under /sign-in.
import { SignIn } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { AuthCanvas } from "@/components/landing/AuthCanvas";
import { clerkEnabled } from "@/lib/clerk";
import { strataClerkAppearance } from "@/lib/clerk-appearance";

export default function SignInPage() {
  if (!clerkEnabled) redirect("/");
  return (
    <AuthCanvas altHref="/sign-up" altLabel="Create account">
      <SignIn appearance={strataClerkAppearance} />
    </AuthCanvas>
  );
}
