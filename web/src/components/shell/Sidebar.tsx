"use client";

/**
 * Persistent left rail. Primary nav is 8 destinations in 4 labelled groups
 * (WORK / MY DATA / STRATA BANK / SOURCES), plus a branded header and an
 * identity/theme footer. Help-tier links (Search, Guides, Contribute) live in
 * the footer, out of the primary nav, so the spine stays scannable.
 *
 * The live library counts that used to ride this rail moved out with the flat
 * LIBRARY group — they now belong to the Explore tabs.
 */

import { Show, SignInButton, UserButton, useUser } from "@clerk/nextjs";
import Link from "next/link";
import type { ReactNode } from "react";

import { SimpleSignInControl } from "@/components/auth/SimpleSignIn";
import { clerkEnabled } from "@/lib/clerk";
import { useUiStore } from "@/stores/ui-store";
import { Logo } from "./Logo";
import { NavItem } from "./NavItem";
import { ThemeToggle } from "./ThemeToggle";
import { hideDecorClass, hideLabelClass } from "./collapse";
import {
  AgentsIcon,
  ConnectorsIcon,
  GuidesIcon,
  HomeIcon,
  IntegrationsIcon,
  PortfolioIcon,
  PyramidIcon,
  SearchIcon,
} from "./icons";

export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);

  return (
    <div className="flex h-full flex-col bg-[var(--bg-1)] border-r border-[var(--border-1)]">
      <SidebarHeader collapsed={collapsed} />

      <nav className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-1" aria-label="Primary">
        <GroupLabel collapsed={collapsed}>Work</GroupLabel>
        <NavItem icon={<HomeIcon />} label="Home" href="/" exact />
        <NavItem icon={<FrameworksLikeBuildIcon />} label="Build" href="/build" />
        <NavItem icon={<PortfolioIcon />} label="Portfolio" href="/portfolio" />

        <GroupLabel collapsed={collapsed}>My data</GroupLabel>
        <NavItem icon={<BankIcon />} label="My Bank" href="/bank" />
        <NavItem icon={<AgentsIcon />} label="Agents" href="/agents" />

        <GroupLabel collapsed={collapsed}>Strata bank</GroupLabel>
        <NavItem icon={<PyramidIcon />} label="Explore" href="/explore" />

        <GroupLabel collapsed={collapsed}>Sources</GroupLabel>
        <NavItem icon={<ConnectorsIcon />} label="Connectors" href="/connectors" />
        <NavItem icon={<IntegrationsIcon />} label="Integrations" href="/integrations" />
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
// "Guest" in the keyless deploy. The secondary help links and theme sit above
// it so the account row anchors the bottom of the rail.
function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const hide = hideLabelClass(collapsed);
  const openPalette = useUiStore((s) => s.openPalette);
  return (
    <div className="shrink-0 border-t border-[var(--border-1)]">
      <div className="px-2 py-2 flex flex-col gap-0.5">
        <SecondaryItem
          icon={<SearchIcon />}
          label="Search"
          onClick={openPalette}
          shortcut="⌘K"
          collapsed={collapsed}
        />
        <SecondaryItem icon={<GuidesIcon />} label="Guides" href="/guides" collapsed={collapsed} />
        <SecondaryItem
          icon={<ContributeIcon />}
          label="Contribute"
          href="/contribute"
          collapsed={collapsed}
        />
      </div>
      <div className="flex items-center gap-2.5 px-3 py-3 border-t border-[var(--border-1)]">
        {clerkEnabled ? <ClerkIdentity hide={hide} /> : <SimpleSignInControl hide={hide} />}
        <ThemeToggle
          className={`shrink-0 ml-auto grid place-items-center w-7 h-7 rounded-[var(--r-2)] text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors ${hideDecorClass(
            collapsed,
          )}`}
        />
      </div>
    </div>
  );
}

// A quieter row than NavItem: smaller, no active accent bar — these are
// help/account-tier links, not primary destinations.
function SecondaryItem({
  icon,
  label,
  href,
  onClick,
  shortcut,
  collapsed,
}: {
  icon: ReactNode;
  label: string;
  href?: string;
  onClick?: () => void;
  shortcut?: string;
  collapsed: boolean;
}) {
  const hide = hideLabelClass(collapsed);
  const inner = (
    <>
      <span className="shrink-0 grid place-items-center w-4 h-4">{icon}</span>
      <span className={`flex-1 truncate text-left ${hide}`}>{label}</span>
      {shortcut && (
        <span className={`font-mono text-[10px] text-[var(--fg-4)] ${hide}`}>{shortcut}</span>
      )}
    </>
  );
  const className =
    "group flex items-center gap-2.5 rounded-[var(--r-2)] px-2.5 py-1.5 text-[12px] text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors";

  if (href) {
    return (
      <Link href={href} className={className}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={`w-full ${className}`}>
      {inner}
    </button>
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
          <button type="button" aria-label="Sign in" className="flex min-w-0 flex-1 items-center gap-2.5 text-left">
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

// Build = the workshop where frameworks compose into TAMs; the layered/branching
// glyph reads as "assemble", distinct from the registry's flat framework list.
function FrameworksLikeBuildIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="6" cy="6" r="2" />
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="12" r="2" />
      <path d="M8 6h4a2 2 0 0 1 2 2v2M8 18h4a2 2 0 0 0 2-2v-2" />
    </svg>
  );
}

// My Bank = the personal, synced store. A wallet/ledger glyph separates the
// private tier from the shared registry's book glyph.
function BankIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18" />
      <path d="M16 14h2" />
    </svg>
  );
}

function ContributeIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
