"use client";

// Zero-config local sign-in for the keyless deploy (see identity-store): the
// sidebar footer shows the signed-in analyst, or a "Sign in" affordance that
// opens a minimal name/org dialog. No external setup, no server round-trip —
// the simple login a single-user analyst tool needs to stop saying "Guest".
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useHasMounted } from "@/lib/use-has-mounted";
import { useIdentityStore } from "@/stores/identity-store";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "·";
}

export function SimpleSignInControl({ hide }: { hide: string }) {
  const mounted = useHasMounted();
  const name = useIdentityStore((s) => s.name);
  const org = useIdentityStore((s) => s.org);
  const signOut = useIdentityStore((s) => s.signOut);
  const [open, setOpen] = useState(false);

  // Before mount the persisted store is empty on both server and client, so
  // render the neutral signed-out state to keep hydration in agreement.
  const signedIn = mounted && !!name;

  if (signedIn) {
    return (
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        <span className="shrink-0 grid place-items-center w-7 h-7 rounded-full bg-[var(--accent)] text-[var(--accent-fg-on)] text-[11px] font-medium">
          {initials(name)}
        </span>
        <div className={`min-w-0 flex-1 leading-tight ${hide}`}>
          <div className="text-[13px] text-[var(--fg-1)] truncate">{name}</div>
          <button
            type="button"
            onClick={signOut}
            className="text-[11px] text-[var(--fg-4)] hover:text-[var(--fg-2)] truncate"
          >
            {org ? `${org} · sign out` : "sign out"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
      >
        <span className="shrink-0 grid place-items-center w-7 h-7 rounded-full bg-[var(--bg-3)] text-[var(--fg-3)] text-[11px] font-medium">
          ↪
        </span>
        <span className={`text-[13px] text-[var(--fg-2)] truncate ${hide}`}>Sign in</span>
      </button>
      {open ? <SignInDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function SignInDialog({ onClose }: { onClose: () => void }) {
  const signIn = useIdentityStore((s) => s.signIn);
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const firstField = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    firstField.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      // Focus trap (WCAG 2.1.2): keep Tab cycling inside the dialog.
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'input, button, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    signIn(name, org);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="strata-signin-title"
      onClick={onClose}
    >
      <form
        ref={dialogRef}
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[360px] rounded-[var(--r-3)] border border-[var(--border-1)] bg-[var(--bg-0)] p-5 shadow-[var(--shadow-overlay)]"
      >
        <h2 id="strata-signin-title" className="text-[15px] font-medium text-[var(--fg-1)]">
          Sign in to Strata
        </h2>
        <p className="mt-1 text-[12px] text-[var(--fg-3)]">
          Used to attribute your saved TAMs and activity. Stored locally on this device.
        </p>
        <label className="mt-4 block text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          Name
        </label>
        <input
          ref={firstField}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jane Vega"
          className="mt-1 w-full rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-2 text-[13px] text-[var(--fg-1)] outline-none focus:border-[var(--accent)]"
        />
        <label className="mt-3 block text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          Organization <span className="text-[var(--fg-4)]">(optional)</span>
        </label>
        <input
          value={org}
          onChange={(e) => setOrg(e.target.value)}
          placeholder="Benchmark"
          className="mt-1 w-full rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-2 text-[13px] text-[var(--fg-1)] outline-none focus:border-[var(--accent)]"
        />
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--r-2)] px-3 py-1.5 text-[13px] text-[var(--fg-2)] hover:bg-[var(--bg-2)]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!name.trim()}
            className="rounded-[var(--r-2)] bg-[var(--accent)] px-3 py-1.5 text-[13px] text-[var(--accent-fg-on)] disabled:opacity-50"
          >
            Sign in
          </button>
        </div>
      </form>
    </div>
  );
}
