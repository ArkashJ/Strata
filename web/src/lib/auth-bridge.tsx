"use client";

/**
 * AuthBridge — wires Clerk's session token into the api-client (PR 1 / U9).
 *
 * `api()` is provider-agnostic: it asks a registered accessor for a token and
 * sends `Authorization: Bearer <token>` only when one comes back. This component
 * registers that accessor from Clerk's `useAuth().getToken`, so every fetch made
 * after sign-in carries the session JWT the backend's Clerk→Principal bridge
 * verifies. When signed out, `getToken()` resolves null → no header → the request
 * falls through to the anonymous path (keyless reads unchanged, KTD-4).
 *
 * Clerk hooks throw without a ClerkProvider, so the hook-using inner component is
 * mounted ONLY when `clerkEnabled`. With Clerk disabled (prod today) nothing
 * registers and the app behaves exactly as before.
 *
 * On the first authenticated load it also runs the one-time localStorage → server
 * migration of the user's favorites (idempotent).
 */

import { useAuth } from "@clerk/nextjs";
import { type ReactNode, useEffect } from "react";

import { setAuthTokenGetter } from "./api-client";
import { clerkEnabled } from "./clerk";
import { migratePersonalDataOnce } from "./personal-migrate";

function ClerkAuthBridge() {
  const { isLoaded, isSignedIn, getToken } = useAuth();

  useEffect(() => {
    // Register a stable accessor. Clerk's `getToken` is memoized per session, so
    // pulling a fresh token on each call keeps short-lived JWTs current.
    setAuthTokenGetter(() => getToken());
    return () => setAuthTokenGetter(null);
  }, [getToken]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    void migratePersonalDataOnce();
  }, [isLoaded, isSignedIn]);

  return null;
}

export function AuthBridge({ children }: { children: ReactNode }) {
  return (
    <>
      {clerkEnabled && <ClerkAuthBridge />}
      {children}
    </>
  );
}
