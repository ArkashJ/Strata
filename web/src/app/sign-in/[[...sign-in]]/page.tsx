// Clerk catch-all sign-in route. The [[...sign-in]] optional-catch-all lets Clerk
// own every sub-path (factor-two, SSO callback, etc.) under /sign-in.
import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-16">
      <SignIn />
    </main>
  );
}
