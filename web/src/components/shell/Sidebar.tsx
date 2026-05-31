"use client";

/**
 * Persistent left rail. Two nav groups (top / LIBRARY) plus a branded header
 * and a contributor footer, matching docs/design/captures/02-sidebar.png.
 *
 * LIBRARY counts are live — one query per surface via useQueries, formatted
 * with Intl.NumberFormat. TAMs has no list endpoint yet, so that count points
 * at /browse as a placeholder.
 */

import { Show, SignInButton, UserButton, useUser } from "@clerk/nextjs";
import { useQueries } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { SimpleSignInControl } from "@/components/auth/SimpleSignIn";
import { Skeleton } from "@/components/ui/Skeleton";
import { clerkEnabled } from "@/lib/clerk";
import { conceptsQuery, frameworksQuery, primitivesQuery, signalsQuery } from "@/lib/queries";
import { useUiStore } from "@/stores/ui-store";
import { Logo } from "./Logo";
import { NavItem } from "./NavItem";
import { ThemeToggle } from "./ThemeToggle";
import { hideDecorClass, hideLabelClass } from "./collapse";
import {
  ConceptsIcon,
  ConnectorsIcon,
  DashboardIcon,
  FrameworksIcon,
  GuidesIcon,
  HomeIcon,
  IntegrationsIcon,
  PortfolioIcon,
  PrimitivesIcon,
  PyramidIcon,
  SearchIcon,
  SignalsIcon,
  TamsIcon,
} from "./icons";

const nf = new Intl.NumberFormat("en-US");

// A library count: the live integer once resolved, a 1-char skeleton while the
// query is pending, or nothing if the value is unavailable.
function Count({
  value,
  pending,
}: {
  value: number | undefined;
  pending: boolean;
}) {
  if (pending) return <Skeleton className="h-3 w-6" />;
  if (value === undefined) return null;
  return <>{nf.format(value)}</>;
}

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const openPalette = useUiStore((s) => s.openPalette);

  const [concepts, primitives, frameworks, signals] = useQueries({
    queries: [conceptsQuery, primitivesQuery, frameworksQuery, signalsQuery],
  });

  return (
    <div className="flex h-full flex-col bg-[var(--bg-1)] border-r border-[var(--border-1)]">
      <SidebarHeader collapsed={collapsed} />

      <nav className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-1" aria-label="Primary">
        <NavItem icon={<HomeIcon />} label="Home" href="/" exact />
        <NavItem icon={<DashboardIcon />} label="Dashboard" href="/dashboard" />
        <NavItem icon={<PyramidIcon />} label="Pyramid explorer" href="/graph" />
        <NavItem icon={<ConnectorsIcon />} label="Connectors" href="/connectors" />
        <NavItem icon={<PortfolioIcon />} label="Portfolio" href="/portfolio" />
        <NavItem icon={<IntegrationsIcon />} label="Integrations" href="/integrations" />
        <NavItem icon={<GuidesIcon />} label="Guides" href="/guides" />
        <NavItem icon={<SearchIcon />} label="Search" onClick={openPalette} />

        <GroupLabel collapsed={collapsed}>Library</GroupLabel>
        <NavItem
          icon={<ConceptsIcon />}
          label="Concepts"
          href="/c"
          count={<Count value={concepts.data?.length} pending={concepts.isPending} />}
        />
        <NavItem
          icon={<PrimitivesIcon />}
          label="Primitives"
          href="/p"
          count={<Count value={primitives.data?.length} pending={primitives.isPending} />}
        />
        <NavItem
          icon={<FrameworksIcon />}
          label="Frameworks"
          href="/f"
          count={<Count value={frameworks.data?.length} pending={frameworks.isPending} />}
        />
        {/* TODO(tams): no list endpoint yet — placeholder until /browse exposes a count. */}
        <NavItem icon={<TamsIcon />} label="TAMs" href="/browse" count={nf.format(0)} />
        {/* Prediction-market signals (Q20): read-only, never feed a TAM. */}
        <NavItem
          icon={<SignalsIcon />}
          label="Signals"
          href="/signals"
          count={<Count value={signals.data?.length} pending={signals.isPending} />}
        />
      </nav>

      <SidebarFooter collapsed={collapsed} />
    </div>
  );
}

function SidebarHeader({ collapsed }: { collapsed: boolean }) {
  const hide = hideLabelClass(collapsed);
  return (
    <div className="h-[var(--topbar-h)] shrink-0 flex items-center gap-2 px-3 border-b border-[var(--border-1)]">
      <Logo />
      <span className={`display italic text-[17px] leading-none text-[var(--fg-1)] ${hide}`}>
        Strata
      </span>
      <span
        aria-hidden="true"
        className={`w-1.5 h-1.5 rounded-full bg-[var(--accent)] ${hideDecorClass(collapsed)}`}
      />
      <span className={`ml-auto font-mono text-[10px] text-[var(--fg-3)] ${hide}`}>v0.42</span>
    </div>
  );
}

// Identity is never fabricated: show the real Clerk user when signed in, a
// Sign-in affordance when Clerk is configured but signed out, and an honest
// "Guest" in the keyless deploy. (Was previously a hard-coded fake contributor.)
function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const hide = hideLabelClass(collapsed);
  return (
    <div className="shrink-0 flex items-center gap-2.5 px-3 py-3 border-t border-[var(--border-1)]">
      {clerkEnabled ? <ClerkIdentity hide={hide} /> : <SimpleSignInControl hide={hide} />}
      <ThemeToggle
        className={`shrink-0 ml-auto grid place-items-center w-7 h-7 rounded-[var(--r-2)] text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors ${hideDecorClass(
          collapsed,
        )}`}
      />
    </div>
  );
}

function Avatar({ children }: { children: ReactNode }) {
  return (
    <span className="shrink-0 grid place-items-center w-7 h-7 rounded-full bg-[var(--bg-3)] text-[var(--fg-3)] text-[11px] font-medium">
      {children}
    </span>
  );
}

function ClerkIdentity({ hide }: { hide: string }) {
  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="modal">
          <button type="button" className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
            <Avatar>↪</Avatar>
            <span className={`text-[13px] text-[var(--fg-2)] truncate ${hide}`}>Sign in</span>
          </button>
        </SignInButton>
      </Show>
      <Show when="signed-in">
        <SignedInIdentity hide={hide} />
      </Show>
    </>
  );
}

function SignedInIdentity({ hide }: { hide: string }) {
  const { user } = useUser();
  const label = user?.fullName ?? user?.primaryEmailAddress?.emailAddress ?? "Account";
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2.5">
      <UserButton appearance={{ elements: { avatarBox: "h-7 w-7" } }} />
      <div className={`min-w-0 leading-tight ${hide}`}>
        <div className="text-[13px] text-[var(--fg-1)] truncate">{label}</div>
      </div>
    </div>
  );
}

function GroupLabel({
  collapsed,
  children,
}: {
  collapsed: boolean;
  children: string;
}) {
  return (
    <div
      className={`px-2.5 pt-4 pb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)] ${hideLabelClass(
        collapsed,
      )}`}
    >
      {children}
    </div>
  );
}
