// Clerk is optional: prod currently runs WITHOUT keys, so every Clerk surface
// (provider, middleware, dashboard auth gate) must degrade gracefully when the
// publishable key is absent — wrapping unconditionally throws at build/runtime.
// The publishable key is the single source of truth; the secret key is a server
// companion that Clerk reads itself, so we only inspect the public flag here so
// the same expression evaluates identically on the server and the client.
export const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
