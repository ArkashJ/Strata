"use client";

/**
 * ⌘K command palette (docs/design/captures/18-search-modal.png). One flat,
 * keyboard-navigable result list assembled from three groups —
 * RECENT (persisted jump-list) then live CONCEPTS / FRAMEWORKS / PRIMITIVES,
 * each ranked by the shared fuzzy scorer. Free text that matches nothing still
 * offers a "size a market" action that routes to the home query (/?q=).
 *
 * Rendered once at the shell root and toggled via the ui-store, so the global
 * ⌘K handler and every Search affordance open the same instance. Built on the
 * native <dialog> element: it gives a real focus trap, ::backdrop, and Escape
 * for free, so the markup stays free of ARIA-role workarounds.
 */

import { useQueries } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { rankByQuery } from "@/lib/fuzzy";
import { conceptsQuery, frameworksQuery, primitivesQuery } from "@/lib/queries";
import { type RecentKind, useUiStore } from "@/stores/ui-store";

// Cap per group so the list stays scannable; the spec mock shows ~2 each.
const PER_GROUP = 5;

type RowKind = RecentKind | "query";

interface Row {
  kind: RowKind;
  label: string;
  // Route target. Detail rows route to /c|/p|/f/{slug}; the query row to /?q=.
  href: string;
  slug?: string;
  badge: string;
}

function groupLabel(kind: RowKind): string {
  switch (kind) {
    case "concept":
      return "Concepts";
    case "framework":
      return "Frameworks";
    case "primitive":
      return "Primitives";
    case "query":
      return "";
  }
}

export function CommandPalette() {
  const open = useUiStore((s) => s.commandPaletteOpen);
  const closePalette = useUiStore((s) => s.closePalette);
  const recents = useUiStore((s) => s.recentEntities);
  const pushRecent = useUiStore((s) => s.pushRecent);
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [concepts, frameworks, primitives] = useQueries({
    queries: [conceptsQuery, frameworksQuery, primitivesQuery],
  });

  // Build the ordered row list. Empty query → RECENT jump-list; otherwise the
  // three live groups ranked by fuzzy score, with a trailing free-text action.
  const rows = buildRows(query, recents, concepts.data, frameworks.data, primitives.data);

  // Mirror the store flag onto the native dialog. showModal() opens the
  // top-layer modal (focus trap + backdrop); close() tears it down.
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) {
      setQuery("");
      setActive(0);
      el.showModal();
      requestAnimationFrame(() => inputRef.current?.focus());
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  // Keep the active index in range as the result set shrinks.
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(rows.length - 1, 0)));
  }, [rows.length]);

  const go = (row: Row | undefined) => {
    if (!row) return;
    if (row.kind !== "query" && row.slug) {
      pushRecent({ kind: row.kind, slug: row.slug, label: row.label });
    }
    closePalette();
    router.push(row.href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a + 1) % rows.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (rows.length ? (a - 1 + rows.length) % rows.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(rows[active]);
    }
  };

  const showHeading = !query.trim() ? recents.length > 0 : true;

  return (
    <dialog
      ref={dialogRef}
      aria-label="Command palette"
      // The dialog's own Escape/backdrop both resolve to the same close path so
      // the store flag never drifts from the element's open state.
      onCancel={(e) => {
        e.preventDefault();
        closePalette();
      }}
      onClick={(e) => {
        if (e.target === dialogRef.current) closePalette();
      }}
      onKeyDown={onKeyDown}
      className="m-0 w-full max-w-[520px] rounded-[var(--r-3)] bg-[var(--bg-1)] p-0 shadow-[var(--shadow-overlay)] backdrop:bg-[rgba(10,10,11,0.32)]"
      style={{ marginTop: "12vh", marginInline: "auto" }}
    >
      <div className="flex h-12 items-center gap-2.5 border-b border-[var(--border-1)] px-4">
        <SearchGlyph />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Jump to concepts, primitives, frameworks, TAMs…"
          aria-label="Search"
          className="flex-1 bg-transparent text-[14px] text-[var(--fg-1)] outline-none placeholder:text-[var(--fg-3)]"
        />
        <button
          type="button"
          onClick={closePalette}
          className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          esc
        </button>
      </div>

      <ul className="max-h-[52vh] overflow-y-auto py-2">
        {rows.length === 0 ? (
          <li className="px-4 py-6 text-center text-[13px] text-[var(--fg-3)]">No matches.</li>
        ) : (
          rows.map((row, i) => {
            const prev = rows[i - 1];
            const heading =
              showHeading && row.kind !== "query" && (!prev || prev.kind !== row.kind)
                ? groupLabel(row.kind)
                : null;
            return (
              <ResultRow
                // Routes are unique per row within a render.
                key={`${row.kind}:${row.slug ?? row.href}`}
                row={row}
                heading={heading}
                active={i === active}
                onHover={() => setActive(i)}
                onSelect={() => go(row)}
              />
            );
          })
        )}
      </ul>
    </dialog>
  );
}

// Assemble the flat, ranked result list. Pure so the dialog body stays readable.
function buildRows(
  query: string,
  recents: { kind: RecentKind; slug: string; label: string }[],
  concepts: { slug: string; name: string }[] | undefined,
  frameworks: { slug: string; name: string; method_family: string }[] | undefined,
  primitives: { slug: string; name: string }[] | undefined,
): Row[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return recents.map((r) => ({
      kind: r.kind,
      label: r.label,
      slug: r.slug,
      href: `/${prefix(r.kind)}/${r.slug}`,
      badge: groupLabel(r.kind),
    }));
  }

  const out: Row[] = [];
  for (const c of rankByQuery(concepts ?? [], trimmed, (x) => x.name).slice(0, PER_GROUP)) {
    out.push({
      kind: "concept",
      label: c.item.name,
      slug: c.item.slug,
      href: `/c/${c.item.slug}`,
      badge: "Concept",
    });
  }
  for (const f of rankByQuery(frameworks ?? [], trimmed, (x) => x.name).slice(0, PER_GROUP)) {
    out.push({
      kind: "framework",
      label: f.item.name,
      slug: f.item.slug,
      href: `/f/${f.item.slug}`,
      badge: f.item.method_family.replace(/_/g, "-"),
    });
  }
  for (const p of rankByQuery(primitives ?? [], trimmed, (x) => x.name).slice(0, PER_GROUP)) {
    out.push({
      kind: "primitive",
      label: p.item.name,
      slug: p.item.slug,
      href: `/p/${p.item.slug}`,
      badge: "Primitive",
    });
  }

  out.push({
    kind: "query",
    label: `Size a market: “${trimmed}”`,
    href: `/?q=${encodeURIComponent(trimmed)}`,
    badge: "Resolve",
  });
  return out;
}

function ResultRow({
  row,
  heading,
  active,
  onHover,
  onSelect,
}: {
  row: Row;
  heading: string | null;
  active: boolean;
  onHover: () => void;
  onSelect: () => void;
}) {
  // Scroll the active row into view as arrow-keys move the selection.
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest" });
  }, [active]);

  return (
    <>
      {heading && (
        <li className="px-4 pb-1 pt-3 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]">
          {heading}
        </li>
      )}
      <li>
        <button
          ref={ref}
          type="button"
          aria-current={active}
          onMouseMove={onHover}
          onClick={onSelect}
          className={`flex w-full items-center gap-3 px-4 py-2 text-left transition-colors ${
            active ? "bg-[var(--accent-tint)]" : ""
          }`}
        >
          <span
            className={`flex-1 truncate text-[13px] ${
              row.kind === "query" ? "text-[var(--accent-active)]" : "text-[var(--fg-1)]"
            }`}
          >
            {row.label}
          </span>
          <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
            {row.badge}
          </span>
        </button>
      </li>
    </>
  );
}

function prefix(kind: RecentKind): string {
  return kind === "concept" ? "c" : kind === "primitive" ? "p" : "f";
}

function SearchGlyph() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--fg-3)"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.2-3.2" />
    </svg>
  );
}
