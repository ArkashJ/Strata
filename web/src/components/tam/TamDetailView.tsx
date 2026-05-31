"use client";

import { ScenarioGraph } from "@/components/ScenarioGraph";
import { TornadoChart } from "@/components/charts/TornadoChart";
import { NetworkGraphModal } from "@/components/network/NetworkGraphModal";
import { TamTrajectoryChart } from "@/components/tam/TamTrajectoryChart";
import { Button } from "@/components/ui/Button";
import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { CountUp, Pulse } from "@/components/ui/motion";
import { ApiError } from "@/lib/api-client";
import { formatCompact, tierLabel } from "@/lib/format";
import { sensitivityQuery, tamQuery, trajectoryQuery } from "@/lib/queries";
import type { TAMOutput } from "@/lib/schemas";
import { isDegenerate, midScenario, tamRange, tamToMarkdown } from "@/lib/tam";
// The frozen TAM artifact page (U6, U11 · design capture 19-tam-detail). The
// most opinionated surface in the product: a TAM is a scenario tree (Q1), so the
// headline is a mid scenario with a low–high band, never a scalar. Provenance is
// non-dismissable (a product principle). All edits fork to a fresh /build state —
// this page is read-only.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "../ui/ErrorState";
import "./tam-print.css";

export function TamDetailView({ hash, initialTam }: { hash: string; initialTam?: TAMOutput }) {
  // `initialTam` is the server-fetched TAM (AC0.8): seeding tanstack's
  // initialData makes the first (server) render paint the real headline into
  // the initial HTML instead of a loading shell, then hydrate seamlessly.
  const tam = useQuery({
    ...tamQuery(hash),
    initialData: initialTam,
    // Mark the server-fetched data fresh so the immutable TAM (staleTime:∞)
    // doesn't trigger a redundant client refetch on every SSR'd page view.
    initialDataUpdatedAt: initialTam ? Date.now() : undefined,
  });

  if (tam.isPending) return <LoadingShell />;

  // A 404 means this hash was never minted; route the user back to the directory.
  if (tam.error instanceof ApiError && tam.error.status === 404) {
    return (
      <Centered>
        <NotFoundState
          label="TAM"
          slug={hash.slice(0, 8)}
          action={
            <Link href="/browse">
              <Button variant="ghost" sm>
                Browse TAMs
              </Button>
            </Link>
          }
        />
      </Centered>
    );
  }

  if (tam.error || !tam.data) {
    return (
      <Centered>
        <ErrorState
          title="Could not load this TAM"
          error={tam.error}
          onRetry={() => tam.refetch()}
        />
      </Centered>
    );
  }

  return <TamArtifact tam={tam.data} />;
}

function TamArtifact({ tam }: { tam: TAMOutput }) {
  const hash8 = tam.state_hash.slice(0, 8);
  const industry = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
  const geo = tam.target.geo ?? "Global";
  const time = tam.target.time ?? "latest";
  const stage = tam.target.expansion_stage;
  const [networkOpen, setNetworkOpen] = useState(false);

  return (
    <main className="tam-artifact mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col px-8 py-8">
      {/* Breadcrumb — TAMs › {industry} › {hash8} (hash is the content-hash short SHA) */}
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 font-mono text-[12px] text-[var(--fg-3)]"
      >
        <Link href="/browse" className="transition-colors hover:text-[var(--fg-1)]">
          TAMs
        </Link>
        <span className="text-[var(--fg-4)]">›</span>
        <span className="capitalize">{industry}</span>
        <span className="text-[var(--fg-4)]">›</span>
        <span className="text-[var(--fg-2)]">{hash8}</span>
      </nav>

      <h1 className="display mt-3 text-[40px] leading-[1.05] text-[var(--fg-1)]">
        {industry} TAM for <span className="italic">{geo}</span>
        {time !== "latest" ? <span>, {time}</span> : null}
      </h1>

      {/* Chips strip — GEO · {time} · STAGE · USD NOMINAL. Currency is stored
          nominal and normalized at query time (Q4); say so explicitly. */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Chip label="GEO" value={geo} />
        <Chip value={time} />
        <Chip label="STAGE" value={stage} />
        <Chip value="USD NOMINAL" />
      </div>

      <p className="mt-3 text-[13px] text-[var(--fg-3)]">
        by <span className="text-[var(--fg-2)]">{tam.created_by}</span>
        <span className="mx-2 text-[var(--fg-4)]">·</span>
        {tam.created_at}
      </p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PermalinkRow hash8={hash8} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" sm onClick={() => setNetworkOpen(true)}>
            Related entities
          </Button>
          <ActionBar tam={tam} />
        </div>
      </div>

      <ProvenanceBanner tam={tam} />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <section className="flex min-w-0 flex-1 flex-col gap-6">
          <MidScenarioCard tam={tam} />
          <ScenarioTree tam={tam} />
          <SensitivitySection slug={tam.target.concept} />
          <TrajectorySection slug={tam.target.concept} />
        </section>

        <RightRail tam={tam} />
      </div>

      <NetworkGraphModal
        rootSlug={tam.target.concept}
        rootName={industry}
        open={networkOpen}
        onClose={() => setNetworkOpen(false)}
      />
    </main>
  );
}

// ── Sensitivity tornado (Wave 2 / AC2.3) ─────────────────────────────────────

function SensitivitySection({ slug }: { slug: string }) {
  const q = useQuery(sensitivityQuery(slug));
  if (q.isPending || q.error || !q.data || q.data.inputs.length === 0) return null;
  return (
    <div>
      <h2 className="display text-[24px] text-[var(--fg-1)]">Sensitivity</h2>
      <p className="mt-1 text-[13px] text-[var(--fg-3)]">
        Which assumption moves the TAM most — each input swung ±{Math.round(q.data.pct * 100)}%.
      </p>
      <div className="mt-3">
        <TornadoChart data={q.data} />
      </div>
    </div>
  );
}

// ── Scenario tree ─────────────────────────────────────────────────────────────

function ScenarioTree({ tam }: { tam: TAMOutput }) {
  // ScenarioGraph is shared and renders each framework node with id
  // `f-${framework}` (ReactFlow exposes that as data-id). We ring the mid leaf
  // without forking the graph by scoping a style rule to that exact data-id —
  // dynamic, so it can't be a static class on the leaf card.
  const midNodeId = `f-${midScenario(tam).framework}`;
  const ringSelector = `.tam-scenario-tree .react-flow__node[data-id="${cssEscape(midNodeId)}"] .canvas-card`;

  return (
    <div className="tam-scenario-tree">
      <style>{`${ringSelector}{box-shadow:0 0 0 2px var(--accent-ring),var(--card-shadow);}`}</style>
      <h2 className="display text-[24px] text-[var(--fg-1)]">Scenario tree</h2>
      <p className="mt-1 text-[13px] text-[var(--fg-3)]">
        {tam.scenarios.length} definitional {tam.scenarios.length === 1 ? "choice" : "choices"}
        {isDegenerate(tam) ? "" : " spanning the low–high band"}. The mid leaf is ringed in accent.
      </p>
      <div className="mt-3">
        <ScenarioGraph tam={tam} />
      </div>
    </div>
  );
}

// Quote a value for safe embedding inside an [data-id="…"] attribute selector.
function cssEscape(value: string): string {
  return value.replace(/["\\]/g, "\\$&");
}

// ── TAM over time ─────────────────────────────────────────────────────────────

// Supplementary, not load-bearing: a failed/empty trajectory fetch leaves the
// rest of the artifact intact, so we render nothing rather than an error card.
function TrajectorySection({ slug }: { slug: string }) {
  const traj = useQuery(trajectoryQuery(slug));

  if (traj.isPending) {
    return (
      <div>
        <h2 className="display text-[24px] text-[var(--fg-1)]">TAM over time</h2>
        <Skeleton className="mt-3 h-[200px] w-full" />
      </div>
    );
  }
  if (traj.error || !traj.data) return null;

  return (
    <div>
      <h2 className="display text-[24px] text-[var(--fg-1)]">TAM over time</h2>
      <p className="mt-1 text-[13px] text-[var(--fg-3)]">
        The TAM re-evaluated at each dated source snapshot — current vs the path it travelled.
      </p>
      <div className="canvas-card mt-3 p-6">
        <TamTrajectoryChart trajectory={traj.data} />
      </div>
    </div>
  );
}

// ── Mid scenario card ─────────────────────────────────────────────────────────

function MidScenarioCard({ tam }: { tam: TAMOutput }) {
  const mid = midScenario(tam);
  const range = tamRange(tam);
  const degenerate = isDegenerate(tam);
  // Spread is the high/low multiple — the headline "~Nx" honesty signal.
  const spread = range.low > 0 ? range.high / range.low : null;
  const leafCount = tam.scenarios.length;

  return (
    <div className="canvas-card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          Triangulated midpoint
        </div>
        <Pulse pulseKey={tam.state_hash} className="tam-num mt-1 inline-block">
          <CountUp
            value={range.mid}
            format={(n) => formatCompact(n, mid.unit)}
            className="text-[44px] leading-[1] text-[var(--fg-1)]"
          />
        </Pulse>
        {degenerate ? (
          <div className="mt-2 text-[13px] text-[var(--fg-3)]">
            Single-method estimate · {leafCount} {leafCount === 1 ? "leaf" : "leaves"}
          </div>
        ) : (
          <div className="mt-2 text-[13px] text-[var(--fg-2)]">
            {formatCompact(range.low, mid.unit)} – {formatCompact(range.high, mid.unit)}
            <span className="mx-1.5 text-[var(--fg-4)]">·</span>
            {leafCount} leaves
            {spread ? (
              <>
                <span className="mx-1.5 text-[var(--fg-4)]">·</span>~{spread.toFixed(1)}× spread
              </>
            ) : null}
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tam.method_families_used.map((mf) => (
            <span
              key={mf}
              className="role-chip uppercase tracking-[0.04em]"
              style={{
                background: "var(--accent-tint)",
                color: "var(--accent-active)",
              }}
            >
              {tierLabel(mf)}
            </span>
          ))}
        </div>
      </div>

      {/* A degenerate TAM has no real independence to show — grey the donut and
          say what it would take to earn a score, rather than fabricate a range. */}
      <div className="shrink-0">
        {degenerate ? (
          <div className="flex flex-col items-center gap-1 opacity-40">
            <IndependenceDonut score={tam.independence_score} size={104} />
            <span className="max-w-[120px] text-center text-[10px] text-[var(--fg-3)]">
              needs ≥2 method families
            </span>
          </div>
        ) : (
          <IndependenceDonut score={tam.independence_score} size={104} />
        )}
      </div>
    </div>
  );
}

// ── Provenance banner ─────────────────────────────────────────────────────────

function ProvenanceBanner({ tam }: { tam: TAMOutput }) {
  const notes: string[] = [];
  if (tam.uses_synthetic_primitives) {
    notes.push("uses a synthetic primitive (range-bounded, expiry-gated) — review before citing.");
  }
  if (tam.uses_modeled_composites) {
    notes.push(
      "uses a community-modeled composite — the result depends on the modeling assumption.",
    );
  }

  // Per-input source tiers are not carried on inputs_used yet, so we cannot count
  // "N of M inputs are community-tier" as the capture does. Surface the gap
  // honestly rather than fabricating a count.
  // TODO(api): expose per-input source tier on inputs_used to render the
  // "N of M inputs are community-tier" provenance count from capture 19.

  if (notes.length === 0) return null;

  return (
    <div
      role="note"
      className="mt-5 flex items-start gap-3 rounded-[var(--r-3)] px-4 py-3 text-[13px] text-[var(--fg-2)]"
      style={{
        background: "var(--tier-analyst-tint)",
        border: "1px solid color-mix(in srgb, var(--warning) 30%, transparent)",
      }}
    >
      <span className="mt-0.5 font-medium text-[var(--warning)]">Provenance</span>
      <span>This TAM {notes.join(" It also ")}</span>
    </div>
  );
}

// ── Right rail ────────────────────────────────────────────────────────────────

function RightRail({ tam }: { tam: TAMOutput }) {
  return (
    <aside className="flex w-full flex-col gap-3 lg:w-[var(--right-rail-w)] lg:shrink-0">
      <RailSection title="Method families used">
        <div className="flex flex-wrap gap-1.5">
          {tam.method_families_used.map((mf) => (
            <span key={mf} className="role-chip uppercase tracking-[0.04em]">
              {tierLabel(mf)}
            </span>
          ))}
        </div>
      </RailSection>

      <RailSection title="Source tier mix">
        {/* Per-input tiers are absent from the API response (see ProvenanceBanner
            TODO), so the capture's stacked tier bar can't be computed yet. */}
        <p className="text-[13px] text-[var(--fg-3)]">
          Per-input source tiers are not yet exposed by the API.
        </p>
        <p className="mt-1 text-[11px] text-[var(--fg-4)]">TODO(api): per-input tier count</p>
      </RailSection>

      <RailSection title="Annotations" badge="0">
        <p className="text-[13px] text-[var(--fg-3)]">No expert annotations on this TAM yet.</p>
      </RailSection>

      <RailSection title="Export">
        <div className="flex flex-col gap-2">
          <DownloadMarkdownButton tam={tam} />
          <Button variant="ghost" sm onClick={() => window.print()} className="justify-start">
            Download PDF
          </Button>
        </div>
      </RailSection>
    </aside>
  );
}

function RailSection({
  title,
  badge,
  children,
}: {
  title: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="canvas-card" style={{ borderRadius: "var(--r-3)" }}>
      <div className="flex items-center justify-between px-4 pt-3">
        <h3 className="text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--fg-3)]">
          {title}
        </h3>
        {badge ? (
          <span className="text-[12px] tabular-nums text-[var(--fg-2)]">{badge}</span>
        ) : null}
      </div>
      <div className="px-4 pb-3 pt-2">{children}</div>
    </section>
  );
}

// ── Action bar + permalink + export ───────────────────────────────────────────

function PermalinkRow({ hash8 }: { hash8: string }) {
  return (
    <div className="flex items-center gap-2 text-[12px] text-[var(--fg-3)]">
      <span>Permalink</span>
      <code className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-2 py-0.5 font-mono text-[var(--fg-2)]">
        {hash8}
      </code>
      <CopyUrlButton />
    </div>
  );
}

function ActionBar({ tam }: { tam: TAMOutput }) {
  const [exportOpen, setExportOpen] = useState(false);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative">
        <Button sm onClick={() => setExportOpen((o) => !o)} aria-expanded={exportOpen}>
          Export
        </Button>
        {exportOpen ? <ExportPopover tam={tam} onClose={() => setExportOpen(false)} /> : null}
      </div>
      {/* /build lands in a later PR — OK if this 404s for now. */}
      <Link href="/build">
        <Button variant="ghost" sm>
          Fork
        </Button>
      </Link>
      <CopyUrlButton variant="ghost" label="Cite" />
      <Button variant="ghost" sm disabled title="Revision history not yet available">
        History
      </Button>
      <Button variant="ghost" sm disabled title="Annotations not yet available">
        0 annotations
      </Button>
    </div>
  );
}

function ExportPopover({
  tam,
  onClose,
}: {
  tam: TAMOutput;
  onClose: () => void;
}) {
  return (
    <div
      role="menu"
      className="absolute left-0 z-10 mt-1 flex w-44 flex-col rounded-[var(--r-3)] border border-[var(--border-1)] bg-[var(--bg-1)] p-1 shadow-[var(--shadow-pop)]"
    >
      <button
        type="button"
        role="menuitem"
        className="rounded-[var(--r-2)] px-3 py-2 text-left text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)]"
        onClick={() => {
          copyCurrentUrl();
          onClose();
        }}
      >
        Copy URL
      </button>
      <button
        type="button"
        role="menuitem"
        className="rounded-[var(--r-2)] px-3 py-2 text-left text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)]"
        onClick={() => {
          downloadMarkdown(tam);
          onClose();
        }}
      >
        Download Markdown
      </button>
      <button
        type="button"
        role="menuitem"
        className="rounded-[var(--r-2)] px-3 py-2 text-left text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)]"
        onClick={() => {
          window.print();
          onClose();
        }}
      >
        Download PDF
      </button>
    </div>
  );
}

function DownloadMarkdownButton({ tam }: { tam: TAMOutput }) {
  return (
    <Button variant="ghost" sm onClick={() => downloadMarkdown(tam)} className="justify-start">
      Download Markdown
    </Button>
  );
}

function copyCurrentUrl() {
  if (typeof window === "undefined") return;
  navigator.clipboard.writeText(window.location.href).catch(() => {});
}

function downloadMarkdown(tam: TAMOutput) {
  if (typeof window === "undefined") return;
  const md = tamToMarkdown(tam);
  const blob = new Blob([md], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `tam-${tam.state_hash.slice(0, 8)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

function CopyUrlButton({
  variant = "ghost",
  label = "Copy",
}: {
  variant?: "primary" | "ghost";
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant={variant}
      sm
      onClick={() => {
        copyCurrentUrl();
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied!" : label}
    </Button>
  );
}

// ── Small bits ────────────────────────────────────────────────────────────────

function Chip({ label, value }: { label?: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[var(--r-round)] bg-[var(--bg-2)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide text-[var(--fg-2)]">
      {label ? <span className="text-[var(--fg-3)]">{label}</span> : null}
      <span className="text-[var(--fg-1)]">{value}</span>
    </span>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col items-center justify-center px-8 py-16">
      {children}
    </main>
  );
}

function LoadingShell() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-6 px-8 py-8">
      <Skeleton className="h-4 w-64" />
      <Skeleton className="h-12 w-2/3" />
      <Skeleton className="h-8 w-96" />
      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="flex flex-1 flex-col gap-6">
          <Skeleton className="h-[180px] w-full" />
          <Skeleton className="h-[420px] w-full" />
        </div>
        <Skeleton className="h-[320px] w-full lg:w-[var(--right-rail-w)]" />
      </div>
    </main>
  );
}
