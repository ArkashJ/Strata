// Clerk catch-all sign-up route, on the Strata night canvas (no app chrome).
// The [[...sign-up]] optional-catch-all lets Clerk own every sub-path
// (verification, SSO callback, etc.) under /sign-up.
import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { AuthCanvas } from "@/components/landing/AuthCanvas";
import { clerkEnabled } from "@/lib/clerk";
import { strataClerkAppearance } from "@/lib/clerk-appearance";

export default function SignUpPage() {
  // No keys → no ClerkProvider → <SignUp/> would be a broken shell. Go home.
  if (!clerkEnabled) redirect("/");
  return (
    <AuthCanvas altHref="/sign-in" altLabel="Sign in">
      <SignUp appearance={strataClerkAppearance} />
    </AuthCanvas>
  );
}
