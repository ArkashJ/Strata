/**
 * ListHeader — the chrome shared by the /c /p /f library list pages: a
 * back-to-Strata link, a title with an optional row count, and a filter input.
 * Kept here (not in a page module) so each list route imports it cleanly. PR2
 * owns the global nav; this is the per-list-page header until then.
 */

"use client";

import Link from "next/link";

export interface ListHeaderProps {
  title: string;
  count?: number;
  filter: string;
  onFilter: (v: string) => void;
  placeholder: string;
}

export function ListHeader({ title, count, filter, onFilter, placeholder }: ListHeaderProps) {
  return (
    <header className="w-full px-8 py-5 flex items-center justify-between gap-6 border-b border-[var(--border-1)]">
      <div className="flex items-baseline gap-3">
        <Link
          href="/"
          className="display text-[20px] text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
        >
          ← Strata
        </Link>
        <span className="text-[var(--fg-4)]">/</span>
        <h1 className="text-[15px] font-medium text-[var(--fg-1)]">{title}</h1>
        {/* The count comes from a client-side query, so it's undefined during
            SSR and known after hydration. Always render the slot (stable DOM
            structure) and let React reconcile the text — suppressHydrationWarning
            marks the SSR-vs-client content difference as intentional, not a bug. */}
        <span suppressHydrationWarning className="text-[13px] text-[var(--fg-3)] tabular-nums">
          {count ?? ""}
        </span>
      </div>
      <input
        type="search"
        value={filter}
        onChange={(e) => onFilter(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-[260px] max-w-[40vw] rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)]"
      />
    </header>
  );
}
