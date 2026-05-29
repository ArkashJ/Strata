"use client";

/**
 * Light/dark switch. Theme is a pure client concern with no server round-trip,
 * so the source of truth is the `dark` class on <html> — set before paint by
 * the no-flash script in layout.tsx and read here via useSyncExternalStore
 * (server snapshot = light, so SSR and hydration agree). Light is the default;
 * the only way into dark is an explicit click, persisted under `strata-theme`.
 */

import { useSyncExternalStore } from "react";

import { isDarkServerSnapshot, isDarkSnapshot, setDarkTheme, subscribeTheme } from "@/lib/theme";
import { MoonIcon, SunIcon } from "./icons";

export function ThemeToggle({ className }: { className?: string }) {
  const dark = useSyncExternalStore(subscribeTheme, isDarkSnapshot, isDarkServerSnapshot);

  return (
    <button
      type="button"
      onClick={() => setDarkTheme(!dark)}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      className={
        className ??
        "grid place-items-center w-8 h-8 rounded-[var(--r-2)] text-[var(--fg-2)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors"
      }
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
