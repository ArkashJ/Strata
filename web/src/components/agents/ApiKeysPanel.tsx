"use client";

/**
 * ApiKeysPanel — API key management + "Connect to Claude" snippets.
 *
 * Three concerns in one panel:
 *   1. Generate a new key (label input + mint button). On success, the FULL
 *      secret is shown once in a copy-and-dismiss box — never re-fetched.
 *   2. List existing keys (masked prefix, dates, revoke per-row).
 *   3. Connect snippets: three copy-ready blocks injecting the most-recently
 *      minted key (or a placeholder if none was just generated).
 *
 * Auth: signed-out users see a prompt instead of the panel. Clerk gating uses
 * the `Show` component (same pattern as AuthControl + SavedBuildsSection).
 */

import { Show, SignInButton } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api-client";
import { clerkEnabled } from "@/lib/clerk";
import { env } from "@/lib/env";
import {
  type ApiKey,
  type ApiKeyCreated,
  apiKeyCreatedSchema,
  apiKeysQuery,
} from "@/lib/queries-api-keys";

// ── Helpers ───────────────────────────────────────────────────────────────────

const dtf = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

function formatDate(iso: string): string {
  try {
    return dtf.format(new Date(iso));
  } catch {
    return iso;
  }
}

// ── CopyBox ───────────────────────────────────────────────────────────────────

function CopyBox({ value, mono = false }: { value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(() => {
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }, [value]);

  return (
    <div className="flex items-start gap-2">
      <pre
        className={`flex-1 overflow-x-auto rounded-[10px] border border-[var(--border-1)] bg-[var(--bg-0)] p-3 text-[12px] leading-[1.6] text-[var(--fg-2)] ${mono ? "font-mono" : ""}`}
      >
        <code>{value}</code>
      </pre>
      <button
        type="button"
        onClick={onCopy}
        className="mt-1 flex-shrink-0 rounded-[var(--r-2)] border border-[var(--border-2)] px-3 py-1.5 text-[12px] text-[var(--fg-2)] transition-colors hover:bg-[var(--bg-2)] active:bg-[var(--bg-3)]"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}

// ── SecretReveal ──────────────────────────────────────────────────────────────

function SecretReveal({ secret, onDismiss }: { secret: string; onDismiss: () => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-[12px] border border-[var(--accent)] bg-[var(--accent-soft)] p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-[var(--accent-active)]">
          Copy this now — you won&apos;t see it again.
        </p>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="flex-shrink-0 text-[var(--fg-3)] transition-colors hover:text-[var(--fg-1)]"
        >
          ✕
        </button>
      </div>
      <CopyBox value={secret} mono />
    </div>
  );
}

// ── MintForm ──────────────────────────────────────────────────────────────────

function MintForm({ onMinted }: { onMinted: (key: ApiKeyCreated) => void }) {
  const [label, setLabel] = useState("");
  const qc = useQueryClient();

  const mint = useMutation({
    mutationFn: async (labelArg: string) => {
      const data = await api<unknown>("/me/api-keys", {
        method: "POST",
        body: JSON.stringify({ label: labelArg || "My key" }),
      });
      // Validate against the canonical POST-response schema (apiKeyCreatedSchema).
      return apiKeyCreatedSchema.parse(data);
    },
    onSuccess: (minted) => {
      onMinted(minted);
      setLabel("");
      void qc.invalidateQueries({ queryKey: ["personal", "api-keys"] });
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        mint.mutate(label);
      }}
      className="flex items-center gap-2"
    >
      <input
        type="text"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Label (optional)"
        maxLength={80}
        className="h-8 flex-1 rounded-[var(--r-2)] border border-[var(--border-1)] bg-[var(--bg-0)] px-3 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:border-[var(--accent)] focus:outline-none"
      />
      <Button type="submit" sm disabled={mint.isPending}>
        {mint.isPending ? "Generating…" : "Generate key"}
      </Button>
      {mint.isError ? (
        <span className="text-[12px] text-[var(--danger)]">Failed — try again</span>
      ) : null}
    </form>
  );
}

// ── KeyRow ────────────────────────────────────────────────────────────────────

function KeyRow({ apiKey, onRevoke }: { apiKey: ApiKey; onRevoke: () => void }) {
  return (
    <li className="flex min-h-[44px] items-center gap-4 border-b border-[var(--border-1)] bg-[var(--bg-1)] px-4 py-2.5 last:border-b-0 hover:bg-[var(--bg-2)]">
      {/* Label */}
      <span className="w-[160px] flex-shrink-0 truncate text-[13px] text-[var(--fg-1)]">
        {apiKey.label || "(no label)"}
      </span>

      {/* Masked prefix */}
      <code className="flex-1 font-mono text-[12px] text-[var(--fg-3)]">
        {apiKey.prefix}••••••••
      </code>

      {/* Created */}
      <span className="w-[110px] flex-shrink-0 text-right font-mono text-[11px] text-[var(--fg-3)]">
        {formatDate(apiKey.created_at)}
      </span>

      {/* Last used */}
      <span className="w-[110px] flex-shrink-0 text-right font-mono text-[11px] text-[var(--fg-3)]">
        {apiKey.last_used_at ? formatDate(apiKey.last_used_at) : "never"}
      </span>

      {/* Revoke */}
      <Button
        variant="ghost"
        sm
        onClick={onRevoke}
        className="flex-shrink-0 text-[var(--danger)] hover:border-[var(--danger)] hover:text-[var(--danger)]"
      >
        Revoke
      </Button>
    </li>
  );
}

// ── KeyList ───────────────────────────────────────────────────────────────────

function KeyList() {
  const q = useQuery(apiKeysQuery);
  const qc = useQueryClient();

  const revoke = useMutation({
    mutationFn: async (keyId: string) => {
      await api(`/me/api-keys/${keyId}`, { method: "DELETE" });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["personal", "api-keys"] });
    },
  });

  function handleRevoke(apiKey: ApiKey) {
    if (!window.confirm(`Revoke key "${apiKey.label || apiKey.prefix}…"? This cannot be undone.`)) {
      return;
    }
    revoke.mutate(apiKey.key_id);
  }

  if (q.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }, (_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder
          <Skeleton key={i} className="h-[44px]" />
        ))}
      </div>
    );
  }

  if (q.error) {
    return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  }

  if (!q.data || q.data.length === 0) {
    return (
      <EmptyState
        title="No API keys yet"
        description="Generate a key above to connect Strata to your agents."
      />
    );
  }

  return (
    <ul
      aria-label="Your API keys"
      className="overflow-hidden rounded-[var(--r-3)] border border-[var(--border-2)]"
    >
      {q.data.map((k) => (
        <KeyRow key={k.key_id} apiKey={k} onRevoke={() => handleRevoke(k)} />
      ))}
    </ul>
  );
}

// ── ConnectSnippets ───────────────────────────────────────────────────────────

function ConnectSnippets({ latestKey }: { latestKey: string | null }) {
  // Trailing slash is load-bearing: the mounted /mcp app 307-redirects /mcp ->
  // /mcp/, and HTTP clients drop the Authorization header across the redirect —
  // so the key silently fails to authenticate. Point clients straight at /mcp/.
  const mcpUrl = `${env.NEXT_PUBLIC_API_URL}/mcp/`;
  const key = latestKey ?? "strata_sk_live_…";
  const hasRealKey = latestKey !== null;

  const claudeCodeSnippet = `claude mcp add --transport http strata ${mcpUrl} --header "Authorization: Bearer ${key}"`;

  const desktopSnippet = JSON.stringify(
    {
      mcpServers: {
        strata: {
          url: mcpUrl,
          headers: { Authorization: `Bearer ${key}` },
        },
      },
    },
    null,
    2,
  );

  // The streamable-HTTP transport requires an explicit Accept (it rejects */*),
  // so a hand-rolled / ChatGPT client must send it — documented here.
  const rawSnippet = `URL: ${mcpUrl}\nHeader: Authorization: Bearer ${key}\nHeader: Accept: application/json, text/event-stream`;

  return (
    <div className="flex flex-col gap-4">
      {!hasRealKey ? (
        <p className="text-[12.5px] text-[var(--fg-3)]">
          Generate a key above, then paste it in place of{" "}
          <code className="font-mono text-[var(--fg-2)]">strata_sk_live_…</code> in the snippets
          below.
        </p>
      ) : null}

      <div className="flex flex-col gap-2">
        <h4 className="text-[12px] text-[var(--fg-2)]">Claude Code</h4>
        <CopyBox value={claudeCodeSnippet} mono />
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-[12px] text-[var(--fg-2)]">Claude Desktop</h4>
        <CopyBox value={desktopSnippet} mono />
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-[12px] text-[var(--fg-2)]">claude.ai / ChatGPT (custom connector)</h4>
        <p className="text-[12px] text-[var(--fg-3)]">
          Settings → Connectors → Add custom connector. Paste the URL below — Claude or ChatGPT runs
          a one-click OAuth sign-in (no header needed). You&apos;ll approve access on a Strata
          consent screen.
        </p>
        <CopyBox value={mcpUrl} mono />
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-[12px] text-[var(--fg-2)]">Raw (any MCP client)</h4>
        <CopyBox value={rawSnippet} mono />
      </div>
    </div>
  );
}

// ── ApiKeysPanel (exported) ───────────────────────────────────────────────────

export function ApiKeysPanel() {
  // `revealed` drives the one-time secret box (dismissable). `mintedKey` keeps
  // the full key for the connect snippets for the rest of the session — so the
  // snippets stay populated after the user dismisses the reveal box, instead of
  // silently reverting to the strata_sk_live_… placeholder.
  const [revealed, setRevealed] = useState<ApiKeyCreated | null>(null);
  const [mintedKey, setMintedKey] = useState<string | null>(null);

  const onMinted = useCallback((k: ApiKeyCreated) => {
    setRevealed(k);
    setMintedKey(k.key);
  }, []);

  // When Clerk is not configured, render a minimal note rather than a broken
  // auth gate — the panel needs a signed-in identity to call /me/api-keys.
  if (!clerkEnabled) {
    return (
      <section className="flex flex-col gap-3 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
        <h2 className="display text-[20px] text-[var(--fg-1)]">API keys</h2>
        <p className="text-[13px] text-[var(--fg-3)]">
          Sign-in is not configured on this deployment. Set{" "}
          <code className="font-mono">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> to enable API key
          management.
        </p>
      </section>
    );
  }

  return (
    <>
      {/* Signed-out: prompt */}
      <Show when="signed-out">
        <section className="flex flex-col gap-3 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
          <h2 className="display text-[20px] text-[var(--fg-1)]">API keys</h2>
          <p className="text-[13px] text-[var(--fg-3)]">
            Sign in to generate an API key and connect Strata to Claude.
          </p>
          <div>
            <SignInButton mode="modal">
              <Button variant="ghost" sm>
                Sign in
              </Button>
            </SignInButton>
          </div>
        </section>
      </Show>

      {/* Signed-in: full panel */}
      <Show when="signed-in">
        <section className="flex flex-col gap-6">
          {/* ── Generate ── */}
          <div className="flex flex-col gap-3 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
            <h2 className="display text-[20px] text-[var(--fg-1)]">API keys</h2>
            <p className="max-w-[640px] text-[13px] text-[var(--fg-3)]">
              Each key authenticates a client against the hosted MCP endpoint. Keep keys secret —
              treat them like passwords.
            </p>

            <MintForm onMinted={onMinted} />

            {revealed ? (
              <SecretReveal secret={revealed.key} onDismiss={() => setRevealed(null)} />
            ) : null}
          </div>

          {/* ── Existing keys ── */}
          <div className="flex flex-col gap-3">
            <h3 className="text-[13px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
              Your keys
            </h3>
            <KeyList />
          </div>

          {/* ── Connect snippets ── */}
          <div className="flex flex-col gap-4 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
            <div className="flex flex-col gap-1">
              <h3 className="display text-[18px] text-[var(--fg-1)]">Connect to Claude</h3>
              <p className="text-[13px] text-[var(--fg-3)]">
                Point any MCP-capable client at the hosted endpoint with your key.
              </p>
            </div>
            <ConnectSnippets latestKey={mintedKey} />
          </div>
        </section>
      </Show>
    </>
  );
}
