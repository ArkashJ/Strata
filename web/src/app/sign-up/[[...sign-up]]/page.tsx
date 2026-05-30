// Clerk catch-all sign-up route. The [[...sign-up]] optional-catch-all lets Clerk
// own every sub-path (verification, SSO callback, etc.) under /sign-up.
import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <SignUp />
    </main>
  );
}
