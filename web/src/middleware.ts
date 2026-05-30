// Auth edge gate. Clerk ships `clerkMiddleware()` for the `middleware.ts`
// convention (it has not adopted Next 16's `proxy.ts` rename), so we keep this
// file name even though Next prints a deprecation notice — switching to proxy.ts
// would break Clerk's own matcher detection.
//
// CRITICAL: prod currently runs WITHOUT Clerk keys. When the publishable key is
// absent we MUST NOT call clerkMiddleware() (it throws on a missing key), so the
// middleware degrades to a pure pass-through. Protection only engages once keys
// are configured.
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { type NextRequest, NextResponse } from "next/server";

import { clerkEnabled } from "@/lib/clerk";

const isProtectedRoute = createRouteMatcher(["/dashboard(.*)"]);

const protect = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export default function middleware(req: NextRequest, event: Parameters<typeof protect>[1]) {
  if (!clerkEnabled) return NextResponse.next();
  return protect(req, event);
}

export const config = {
  // Skip Next internals and static assets; run on everything else (Clerk's
  // recommended matcher). Inert when clerkEnabled is false.
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
