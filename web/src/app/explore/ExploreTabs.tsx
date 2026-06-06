"use client";

/**
 * The Explore tab strip. Standard underline-tab pattern: the active tab carries
 * the accent underline + ink text, idle tabs sit at fg-2 and brighten on hover.
 * Active state is path-based (startsWith) so a detail route under a tab keeps it
 * lit. Marked as a tablist for assistive tech; keyboard order follows the DOM.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { label: "Concepts", href: "/explore/concepts" },
  { label: "Primitives", href: "/explore/primitives" },
  { label: "Frameworks", href: "/explore/frameworks" },
  { label: "Signals", href: "/explore/signals" },
  { label: "Pyramid", href: "/explore/pyramid" },
  { label: "TAMs", href: "/explore/tams" },
] as const;

export function ExploreTabs() {
  const pathname = usePathname();

  return (
    <div role="tablist" aria-label="Explore sections" className="mt-5 flex gap-1 overflow-x-auto">
      {TABS.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            role="tab"
            aria-selected={active}
            aria-current={active ? "page" : undefined}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2.5 text-[13px] font-medium transition-colors ${
              active
                ? "border-[var(--accent)] text-[var(--fg-1)]"
                : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
