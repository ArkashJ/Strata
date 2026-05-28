"use client";

/**
 * One sidebar row: icon + label + optional right-aligned count. Active state is
 * derived from the current path (startsWith, so /c/foo keeps Concepts lit) and
 * paints an accent-tint fill plus a 2px left accent bar.
 *
 * A row can be a link (most rows) or a plain button (Search → opens palette),
 * so it takes either an `href` or an `onClick`.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useUiStore } from "@/stores/ui-store";

import { hideLabelClass } from "./collapse";

interface NavItemProps {
  icon: ReactNode;
  label: string;
  href?: string;
  onClick?: () => void;
  count?: ReactNode;
  // Override path-based active detection (e.g. Home must match "/" exactly).
  exact?: boolean;
}

function useIsActive(href: string | undefined, exact: boolean): boolean {
  const pathname = usePathname();
  if (!href) return false;
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavItem({ icon, label, href, onClick, count, exact = false }: NavItemProps) {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const active = useIsActive(href, exact);
  const hide = hideLabelClass(collapsed);

  const inner = (
    <>
      <span
        aria-hidden="true"
        className={`absolute left-0 top-1 bottom-1 w-[2px] rounded-r-full bg-[var(--accent)] transition-opacity ${
          active ? "opacity-100" : "opacity-0"
        }`}
      />
      <span className="shrink-0 grid place-items-center w-4 h-4">{icon}</span>
      <span className={`flex-1 truncate text-left ${hide}`}>{label}</span>
      {count !== undefined && (
        <span className={`font-mono text-[11px] tabular-nums text-[var(--fg-3)] ${hide}`}>
          {count}
        </span>
      )}
    </>
  );

  const className = `group relative flex items-center gap-2.5 rounded-[var(--r-2)] px-2.5 py-1.5 text-[13px] transition-colors ${
    active
      ? "bg-[var(--accent-tint)] text-[var(--accent-active)] font-medium"
      : "text-[var(--fg-2)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)]"
  }`;

  if (href) {
    return (
      <Link href={href} className={className} aria-current={active ? "page" : undefined}>
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
