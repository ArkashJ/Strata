"use client";

/**
 * Top chrome bar (docs/design/captures/03-topbar.png). The left "search field"
 * is deliberately a button, not an <input> — typing happens in the command
 * palette, so this is just a click target that opens it. The hamburger is
 * visible only below `md`, where the sidebar becomes an off-canvas drawer.
 */

import { useUiStore } from "@/stores/ui-store";

import { ThemeToggle } from "./ThemeToggle";
import { BellIcon, MenuIcon, SearchIcon } from "./icons";

export function TopBar() {
  const openPalette = useUiStore((s) => s.openPalette);
  const setDrawerOpen = useUiStore((s) => s.setDrawerOpen);

  return (
    <header className="h-[var(--topbar-h)] shrink-0 flex items-center gap-3 px-4 border-b border-[var(--border-1)] bg-[var(--bg-1)]">
      <button
        type="button"
        aria-label="Open navigation"
        onClick={() => setDrawerOpen(true)}
        className="md:hidden grid place-items-center w-8 h-8 rounded-[var(--r-2)] text-[var(--fg-2)] hover:bg-[var(--bg-2)] transition-colors"
      >
        <MenuIcon />
      </button>

      <button
        type="button"
        onClick={openPalette}
        aria-label="Search concepts, primitives, frameworks, TAMs"
        className="group flex items-center gap-2.5 h-8 max-w-[520px] flex-1 px-3 rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] text-left hover:border-[var(--border-3)] transition-colors"
      >
        <SearchIcon className="text-[var(--fg-3)]" />
        <span className="flex-1 truncate text-[13px] text-[var(--fg-3)]">
          Search concepts, primitives, frameworks, TAMs…
        </span>
        <kbd className="hidden sm:inline-flex items-center rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-3)]">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        <IconButton label="Notifications">
          <BellIcon />
        </IconButton>
        <ThemeToggle />
      </div>
    </header>
  );
}

function IconButton({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      className="grid place-items-center w-8 h-8 rounded-[var(--r-2)] text-[var(--fg-2)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors"
    >
      {children}
    </button>
  );
}
