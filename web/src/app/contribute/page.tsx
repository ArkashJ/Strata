"use client";

// /contribute — the contribution intake (Phase 5). A form that submits a proposed
// primitive to POST /contribute, which runs the SAME validator the committed bank
// uses and returns accepted / needs_review / rejected with reasons. Low-tier
// sources are never auto-published (they queue for human review) — the honesty
// gate that keeps an unsourced number from ever reaching a TAM.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api-client";

const TIERS = [
  "first_party",
  "regulator",
  "aggregator",
  "analyst",
  "analyst-paraphrase",
  "community",
  "community-modeled",
] as const;

const UNIT_KINDS = ["stock", "flow", "intensive", "dimensionless"] as const;
const UNIT_DIMENSIONS = [
  "people",
  "currency",
  "organizations",
  "transactions",
  "events",
  "percent",
  "seats",
] as const;

interface Result {
  status: "accepted" | "needs_review" | "rejected";
  reasons: string[];
  contribution_id: number | null;
}

const STATUS_STYLE: Record<Result["status"], string> = {
  accepted: "text-[var(--success)]",
  needs_review: "text-[var(--warning)]",
  rejected: "text-[var(--danger,#e05a5a)]",
};

const FIELD =
  "rounded-[8px] border border-[var(--border-1)] bg-[var(--bg-0)] px-3 py-2 text-[13px] text-[var(--fg-1)]";

export default function ContributePage() {
  const [f, setF] = useState({
    slug: "",
    concept_slug: "",
    name: "",
    description: "",
    value: "",
    unit_kind: "stock",
    unit_dimension: "people",
    currency: "",
    as_of: "",
    tier: "regulator",
    url: "",
    sha256: "",
  });

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF((prev) => ({ ...prev, [k]: e.target.value }));

  const mut = useMutation({
    mutationFn: async (): Promise<Result> => {
      const unit: Record<string, string> = { kind: f.unit_kind, dimension: f.unit_dimension };
      if (f.unit_dimension === "currency" && f.currency) unit.currency = f.currency;
      const payload = {
        kind: "atomic_primitive",
        slug: f.slug,
        schema_version: 1,
        concept_slug: f.concept_slug,
        name: f.name,
        description: f.description,
        value: Number(f.value),
        unit,
        as_of: f.as_of,
        geo: { level: "country", codes: ["US"] },
        geo_perspective: "supply",
        distribution_shape: "normal",
        delivery_mode: "n/a",
        source: {
          slug: `${f.slug}-src`,
          tier: f.tier,
          url: f.url,
          accessed: f.as_of,
          snapshot_sha256: f.sha256,
        },
        visibility: "private",
      };
      return api("/contribute", {
        method: "POST",
        body: JSON.stringify({ kind: "atomic_primitive", payload }),
      });
    },
  });

  return (
    <main className="mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-6 px-8 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="display text-[32px] leading-[1.05] text-[var(--fg-1)]">
          Contribute a primitive
        </h1>
        <p className="text-[14px] text-[var(--fg-3)]">
          Propose a sourced number. It runs through the same validator the committed bank uses —
          schema, unit signature, a real source URL + SHA-256 snapshot, no future date. Regulator /
          first-party sources auto-accept (org-private first); everything else queues for review. We
          never auto-publish an unsourced number.
        </p>
      </header>

      <form
        className="grid grid-cols-1 gap-3 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          mut.mutate();
        }}
      >
        <input
          className={FIELD}
          placeholder="slug (kebab-case)"
          value={f.slug}
          onChange={set("slug")}
          required
        />
        <input
          className={FIELD}
          placeholder="concept_slug"
          value={f.concept_slug}
          onChange={set("concept_slug")}
          required
        />
        <input
          className={`${FIELD} sm:col-span-2`}
          placeholder="name"
          value={f.name}
          onChange={set("name")}
          required
        />
        <input
          className={`${FIELD} sm:col-span-2`}
          placeholder="description"
          value={f.description}
          onChange={set("description")}
          required
        />
        <input
          className={FIELD}
          type="number"
          step="any"
          placeholder="value"
          value={f.value}
          onChange={set("value")}
          required
        />
        <input className={FIELD} type="date" value={f.as_of} onChange={set("as_of")} required />
        <select className={FIELD} value={f.unit_kind} onChange={set("unit_kind")}>
          {UNIT_KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <select className={FIELD} value={f.unit_dimension} onChange={set("unit_dimension")}>
          {UNIT_DIMENSIONS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        {f.unit_dimension === "currency" ? (
          <input
            className={FIELD}
            placeholder="currency (e.g. USD)"
            value={f.currency}
            onChange={set("currency")}
          />
        ) : null}
        <select className={FIELD} value={f.tier} onChange={set("tier")}>
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          className={`${FIELD} sm:col-span-2`}
          placeholder="source URL (real host)"
          value={f.url}
          onChange={set("url")}
          required
        />
        <input
          className={`${FIELD} sm:col-span-2`}
          placeholder="snapshot_sha256 (64 hex chars)"
          value={f.sha256}
          onChange={set("sha256")}
          required
        />

        <button
          type="submit"
          disabled={mut.isPending}
          className="rounded-[8px] bg-[var(--accent)] px-4 py-2 text-[13px] font-medium text-[var(--bg-0)] hover:opacity-90 disabled:opacity-50 sm:col-span-2"
        >
          {mut.isPending ? "Validating…" : "Validate & submit"}
        </button>
      </form>

      {mut.data ? (
        <div className="rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
          <div className={`text-[15px] font-medium ${STATUS_STYLE[mut.data.status]}`}>
            {mut.data.status.replace("_", " ")}
            {mut.data.contribution_id !== null ? ` · #${mut.data.contribution_id}` : ""}
          </div>
          <ul className="mt-2 flex flex-col gap-1 text-[13px] text-[var(--fg-2)]">
            {mut.data.reasons.map((r) => (
              <li key={r}>• {r}</li>
            ))}
          </ul>
        </div>
      ) : mut.error ? (
        <div className="rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5 text-[13px] text-[var(--danger,#e05a5a)]">
          {String(mut.error)}
        </div>
      ) : null}
    </main>
  );
}
