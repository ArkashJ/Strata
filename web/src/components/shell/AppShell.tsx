"use client";

/**
 * The whole-app chrome: a fixed sidebar beside a column of TopBar over a
 * scrollable <main>. Wraps every route's content. Owns the global ⌘K / Ctrl+K
 * shortcut and always renders the command palette so any Search affordance
 * opens the same instance.
 *
 *   ┌── grid [auto 1fr] ──────────────────────────┐
 *   │ Sidebar │ TopBar                             │
 *   │ (fixed) ├────────────────────────────────────┤
 *   │         │ <main> (scrolls)                   │
 *   └─────────┴────────────────────────────────────┘
 *
 * Below `lg` the sidebar collapses to an icon rail; below `md` it leaves the
 * grid entirely and becomes an off-canvas drawer toggled from the TopBar. Every
 * route — landing included — renders inside this chrome (see
 * docs/design/captures/01-home-fullpage.png).
 */

import { Show } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { CommandPalette } from "@/components/CommandPalette";
import { clerkEnabled } from "@/lib/clerk";
import { useUiStore } from "@/stores/ui-store";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

// Chooses the chrome. The sidebar + topbar only ever wrap the signed-in app.
// Auth pages (/sign-in, /sign-up) and the signed-out landing render bare — they
// own a full-screen night canvas. The keyless dev build keeps the full shell.
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const bareRoute = pathname.startsWith("/sign-in") || pathname.startsWith("/sign-up");

  if (!clerkEnabled) return <FullShell>{children}</FullShell>;
  if (bareRoute) return <>{children}</>;

  // "/" is public: signed-out gets the marketing landing (its own canvas, no
  // chrome), signed-in gets the app home in the full shell.
  if (pathname === "/") {
    return (
      <>
        <Show when="signed-out">{children}</Show>
        <Show when="signed-in">
          <FullShell>{children}</FullShell>
        </Show>
      </>
    );
  }

  // Every other route is gated — middleware redirects signed-out visitors before
  // they reach here, so always render the full shell (no load flash, no bare leak).
  return <FullShell>{children}</FullShell>;
}

function FullShell({ children }: { children: ReactNode }) {
  const togglePalette = useUiStore((s) => s.togglePalette);
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const drawerOpen = useUiStore((s) => s.drawerOpen);
  const setDrawerOpen = useUiStore((s) => s.setDrawerOpen);

  // Global palette shortcut. Registered once at the shell root.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        togglePalette();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePalette]);

  // First grid column is `auto` so it tracks the aside's real width — the icon
  // rail below `lg`, or zero below `md` where the sidebar leaves the flow and
  // becomes a drawer. The `sidebarCollapsed` flag forces the rail at lg+ too.
  return (
    <div className="grid h-dvh grid-cols-[auto_1fr] overflow-hidden">
      {/* Inline sidebar (md and up). */}
      <aside
        className={`hidden overflow-hidden md:block w-[var(--sidebar-w-collapsed)] ${
          collapsed ? "" : "lg:w-[var(--sidebar-w)]"
        }`}
      >
        <Sidebar />
      </aside>

      {/* Off-canvas drawer (below md). */}
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Sidebar />
      </MobileDrawer>

      <div className="flex min-w-0 flex-col overflow-hidden">
        <TopBar />
        <main className="flex flex-1 flex-col overflow-y-auto bg-[var(--bg-0)]">{children}</main>
      </div>

      <CommandPalette />
    </div>
  );
}

function MobileDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  // Close on Escape while the drawer is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex md:hidden">
      {/* A real <button> scrim is focusable and keyboard-dismissable, so the
          click-to-close affordance needs no ARIA workaround. */}
      <button
        type="button"
        aria-label="Close navigation"
        onClick={onClose}
        className="absolute inset-0 bg-[rgba(10,10,11,0.32)]"
      />
      <div className="relative h-full w-[var(--sidebar-w)] max-w-[82vw] shadow-[var(--shadow-overlay)]">
        {children}
      </div>
    </div>
  );
}
