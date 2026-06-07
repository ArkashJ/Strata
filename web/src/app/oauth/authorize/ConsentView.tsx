"use client";

/**
 * ConsentView — the Clerk-gated OAuth consent screen.
 *
 * The backend `GET /oauth/authorize` validates the request (redirect_uri exact
 * match + trusted-host allowlist, PKCE S256, resource audience) and 302s the
 * browser here with the OAuth params on the query string. This page:
 *   1. Requires a Clerk session (signed-out → sign-in prompt).
 *   2. Shows what is being granted ("Allow <connector> to access your Strata
 *      org?") using the REAL Clerk identity — never an auto-consented demo org.
 *   3. On Approve/Deny, POSTs the decision to the backend WITH the Clerk session
 *      token; the backend mints a single-use code (or an access_denied error)
 *      and returns the connector callback to navigate to.
 *
 * The Clerk token is fetched explicitly via `getToken()` and sent as the Bearer
 * so the decision call does not depend on the global auth bridge being mounted.
 */

import { Show, SignInButton, useAuth, useUser } from "@clerk/nextjs";
import { useSearchParams } from "next/navigation";
import { type ReactNode, useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { clerkEnabled } from "@/lib/clerk";
import { env } from "@/lib/env";

// Map a registered callback host to a human connector name for the consent copy.
function connectorName(redirectUri: string): string {
  try {
    const host = new URL(redirectUri).hostname;
    if (host === "claude.ai") return "Claude";
    if (host === "chatgpt.com" || host === "chat.openai.com") return "ChatGPT";
    if (host === "localhost" || host === "127.0.0.1") return "Claude Code (local)";
    return host;
  } catch {
    return "an application";
  }
}

interface OAuthParams {
  response_type: string;
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  code_challenge_method: string;
  resource: string;
  scope: string;
  state: string | null;
}

function readParams(sp: URLSearchParams): OAuthParams | null {
  const client_id = sp.get("client_id");
  const redirect_uri = sp.get("redirect_uri");
  const code_challenge = sp.get("code_challenge");
  const resource = sp.get("resource");
  if (!client_id || !redirect_uri || !code_challenge || !resource) return null;
  return {
    response_type: sp.get("response_type") || "code",
    client_id,
    redirect_uri,
    code_challenge,
    code_challenge_method: sp.get("code_challenge_method") || "S256",
    resource,
    scope: sp.get("scope") || "*",
    state: sp.get("state"),
  };
}

function Card({ children }: { children: ReactNode }) {
  return (
    <main className="flex-1 flex items-center justify-center p-6">
      <section className="flex w-full max-w-[440px] flex-col gap-5 rounded-[16px] border border-[var(--border-2)] bg-[var(--bg-1)] p-7">
        {children}
      </section>
    </main>
  );
}

export function ConsentView() {
  const sp = useSearchParams();
  const { getToken } = useAuth();
  const { user } = useUser();
  const params = useMemo(() => readParams(sp), [sp]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = useCallback(
    async (approve: boolean) => {
      if (!params) return;
      setBusy(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) {
          setError("Your session expired — sign in again.");
          setBusy(false);
          return;
        }
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/oauth/authorize/decision`, {
          method: "POST",
          headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
          body: JSON.stringify({ ...params, approve }),
        });
        if (!res.ok) {
          setError("Could not complete the request. Please try again.");
          setBusy(false);
          return;
        }
        const data = (await res.json()) as { redirect_to: string };
        // Hand the browser back to the connector's callback (code or error).
        window.location.href = data.redirect_to;
      } catch {
        setError("Network error — please try again.");
        setBusy(false);
      }
    },
    [params, getToken],
  );

  // Clerk not configured on this deployment — the consent flow needs an identity.
  if (!clerkEnabled) {
    return (
      <Card>
        <h1 className="display text-[22px] text-[var(--fg-1)]">Connect Strata</h1>
        <p className="text-[13px] text-[var(--fg-3)]">
          Sign-in is not configured on this deployment, so the connector flow is unavailable.
        </p>
      </Card>
    );
  }

  if (!params) {
    return (
      <Card>
        <h1 className="display text-[22px] text-[var(--fg-1)]">Invalid request</h1>
        <p className="text-[13px] text-[var(--fg-3)]">
          This authorization link is missing required parameters. Start the connection again from
          your client&apos;s connector settings.
        </p>
      </Card>
    );
  }

  const connector = connectorName(params.redirect_uri);
  const account =
    user?.primaryEmailAddress?.emailAddress ?? user?.fullName ?? "your Strata account";

  return (
    <>
      <Show when="signed-out">
        <Card>
          <h1 className="display text-[22px] text-[var(--fg-1)]">Sign in to connect</h1>
          <p className="text-[13px] text-[var(--fg-3)]">
            Sign in to your Strata account to let{" "}
            <span className="text-[var(--fg-1)]">{connector}</span> connect.
          </p>
          <div>
            <SignInButton mode="modal">
              <Button>Sign in</Button>
            </SignInButton>
          </div>
        </Card>
      </Show>

      <Show when="signed-in">
        <Card>
          <div className="flex flex-col gap-2">
            <h1 className="display text-[22px] leading-tight text-[var(--fg-1)]">
              Allow {connector} to access your Strata org?
            </h1>
            <p className="text-[13px] text-[var(--fg-3)]">
              <span className="text-[var(--fg-1)]">{connector}</span> is requesting access to your
              sourced market data, frameworks, and saved work as{" "}
              <span className="font-mono text-[12px] text-[var(--fg-2)]">{account}</span>.
            </p>
          </div>

          <div className="rounded-[10px] border border-[var(--border-1)] bg-[var(--bg-0)] p-3 text-[12px] leading-[1.6] text-[var(--fg-3)]">
            It can read and build on the data your organization can see. It cannot change your
            account or billing. You can disconnect it from your client at any time.
          </div>

          {error ? <p className="text-[12px] text-[var(--danger)]">{error}</p> : null}

          <div className="flex items-center gap-3">
            <Button onClick={() => void decide(true)} disabled={busy}>
              {busy ? "Connecting…" : `Allow ${connector}`}
            </Button>
            <Button variant="ghost" onClick={() => void decide(false)} disabled={busy}>
              Deny
            </Button>
          </div>
        </Card>
      </Show>
    </>
  );
}
