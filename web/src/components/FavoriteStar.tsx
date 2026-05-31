"use client";

// A star toggle for favoriting a TAM build. Renders as its own button (a sibling
// of the row link, never nested inside it) so it doesn't swallow the row's click.
import type { BuildHistoryEntry } from "@/lib/build-history";
import { useHasMounted } from "@/lib/use-has-mounted";
import { useFavoritesStore } from "@/stores/favorites-store";

export function FavoriteStar({ entry, className = "" }: { entry: BuildHistoryEntry; className?: string }) {
  const mounted = useHasMounted();
  // Subscribe to the derived boolean for this hash so each star reacts only to
  // its own key (hook is always called; the value is gated on mount).
  const favorited = useFavoritesStore((s) => !!s.items[entry.hash]);
  const toggle = useFavoritesStore((s) => s.toggle);
  // Before mount the persisted store is empty on server + first client render.
  const active = mounted && favorited;

  return (
    <button
      type="button"
      onClick={() => toggle(entry)}
      aria-pressed={active}
      aria-label={active ? "Remove from favorites" : "Add to favorites"}
      title={active ? "Remove from favorites" : "Add to favorites"}
      className={`grid h-8 w-8 shrink-0 place-items-center rounded-[var(--r-2)] transition-colors hover:bg-[var(--bg-2)] ${className}`}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill={active ? "var(--accent)" : "none"}
        stroke={active ? "var(--accent)" : "currentColor"}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={active ? "" : "text-[var(--fg-3)]"}
        aria-hidden="true"
      >
        <path d="M12 17.3 6.2 20.5l1.1-6.4L2.6 9.5l6.5-.9L12 2.7l2.9 5.9 6.5.9-4.7 4.6 1.1 6.4z" />
      </svg>
    </button>
  );
}
