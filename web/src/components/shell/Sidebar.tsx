"use client";

/**
 * Persistent left rail. Three nav groups (top / LIBRARY / COMMUNITY) plus a
 * branded header and a contributor footer, matching docs/design/captures/
 * 02-sidebar.png.
 *
 * LIBRARY counts are live — one query per surface via useQueries, formatted
 * with Intl.NumberFormat. TAMs has no list endpoint yet, and the whole
 * COMMUNITY group is pre-auth, so those counts are static placeholders flagged
 * for follow-up.
 */

import { useQueries } from "@tanstack/react-query";

import { Skeleton } from "@/components/ui/Skeleton";
import { conceptsQuery, frameworksQuery, primitivesQuery } from "@/lib/queries";
import { useUiStore } from "@/stores/ui-store";
import { Logo } from "./Logo";
import { NavItem } from "./NavItem";
import { hideDecorClass, hideLabelClass } from "./collapse";
import {
  ActivityIcon,
  AnnotationsIcon,
  ConceptsIcon,
  FrameworksIcon,
  HomeIcon,
  PrimitivesIcon,
  PullRequestIcon,
  PyramidIcon,
  SearchIcon,
  SettingsIcon,
  StarIcon,
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

  const [concepts, primitives, frameworks] = useQueries({
    queries: [conceptsQuery, primitivesQuery, frameworksQuery],
  });

  return (
    <div className="flex h-full flex-col bg-[var(--bg-1)] border-r border-[var(--border-1)]">
      <SidebarHeader collapsed={collapsed} />

      <nav className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-1" aria-label="Primary">
        <NavItem icon={<HomeIcon />} label="Home" href="/" exact />
        <NavItem icon={<PyramidIcon />} label="Pyramid explorer" href="/graph" />
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

        <GroupLabel collapsed={collapsed}>Community</GroupLabel>
        {/* TODO(community): static counts — wire to the contribution API in a later PR. */}
        <NavItem icon={<PullRequestIcon />} label="Pull requests" href="/contribute" count="—" />
        <NavItem icon={<AnnotationsIcon />} label="Annotations" href="/contribute" count="—" />
        <NavItem icon={<ActivityIcon />} label="Activity" href="/contribute" />
        <NavItem icon={<StarIcon />} label="Starred" href="/contribute" />
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

// TODO(auth): hard-coded contributor — replace with the signed-in user.
function SidebarFooter({ collapsed }: { collapsed: boolean }) {
  const hide = hideLabelClass(collapsed);
  return (
    <div className="shrink-0 flex items-center gap-2.5 px-3 py-3 border-t border-[var(--border-1)]">
      <span className="shrink-0 grid place-items-center w-7 h-7 rounded-full bg-[var(--accent)] text-[var(--accent-fg-on)] text-[11px] font-medium">
        JV
      </span>
      <div className={`min-w-0 flex-1 leading-tight ${hide}`}>
        <div className="text-[13px] text-[var(--fg-1)] truncate">j.vega</div>
        <div className="text-[11px] text-[var(--fg-3)] truncate">verified · 27 contribs</div>
      </div>
      <button
        type="button"
        aria-label="Settings"
        className={`shrink-0 grid place-items-center w-7 h-7 rounded-[var(--r-2)] text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors ${hideDecorClass(
          collapsed,
        )}`}
      >
        <SettingsIcon />
      </button>
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
