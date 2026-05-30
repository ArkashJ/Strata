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
import { type NextFetchEvent, type NextRequest, NextResponse } from "next/server";

import { clerkEnabled } from "@/lib/clerk";

// The Clerk handler's call signature, declared inline to avoid the deprecated
// `NextMiddleware` type import.
type MiddlewareFn = (
  req: NextRequest,
  event: NextFetchEvent,
) => Response | Promise<Response | undefined> | undefined;

// Build the Clerk handler LAZILY — `clerkMiddleware()` reads the publishable key
// at construction time, so calling it at module scope would run on every Edge
// cold-start, including keyless prod. We only construct it once, inside the guard,
// after confirming keys exist. Cached so it's built at most once per worker.
let _protect: MiddlewareFn | null = null;

function getProtect(): MiddlewareFn {
  if (!_protect) {
    const isProtectedRoute = createRouteMatcher(["/dashboard(.*)"]);
    _protect = clerkMiddleware(async (auth, req) => {
      if (isProtectedRoute(req)) {
        await auth.protect();
      }
    }) as unknown as MiddlewareFn;
  }
  return _protect;
}

export default function middleware(req: NextRequest, event: NextFetchEvent) {
  if (!clerkEnabled) return NextResponse.next();
  return getProtect()(req, event);
}

export const config = {
  // Skip Next internals and static assets; run on everything else (Clerk's
  // recommended matcher). Inert when clerkEnabled is false.
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
