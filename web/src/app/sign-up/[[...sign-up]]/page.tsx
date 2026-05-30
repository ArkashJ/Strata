// Clerk catch-all sign-up route. The [[...sign-up]] optional-catch-all lets Clerk
// own every sub-path (verification, SSO callback, etc.) under /sign-up.
import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";

import { clerkEnabled } from "@/lib/clerk";

export default function SignUpPage() {
  // No keys → no ClerkProvider → <SignUp/> would be a broken shell. Go home.
  if (!clerkEnabled) redirect("/");
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <SignUp />
    </main>
  );
}
