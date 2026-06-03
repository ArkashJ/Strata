// /agents — the Strata MCP harness surface. A Server Component documenting the
// read-only + write + live tools an AI agent can call to do sourced market
// research against the data bank. Mirrors the catalog in backend mcp/tools.py.
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent harness · Strata",
  description:
    "Give your AI agent sourced, hash-pinned market data. The Strata MCP server exposes the data bank, frameworks, and live connectors as callable tools.",
};

type ToolKind = "read" | "write" | "live";

interface Tool {
  name: string;
  kind: ToolKind;
  blurb: string;
}

// Kept in sync with backend `mcp/tools.py` TOOLS (the server is the source of truth).
const TOOLS: Tool[] = [
  {
    name: "search_concepts",
    kind: "read",
    blurb: "Find curated markets; each returns its sourced measurements.",
  },
  {
    name: "list_primitives",
    kind: "read",
    blurb: "Browse the sourced data bank — filter by tier, dimension, or query.",
  },
  {
    name: "get_primitive",
    kind: "read",
    blurb: "One atomic number with value, unit, and source citation.",
  },
  {
    name: "list_frameworks",
    kind: "read",
    blurb: "The TAM recipes (method family, lens, inputs, formula).",
  },
  {
    name: "size_tam",
    kind: "read",
    blurb: "Size a concept into a sourced, hash-pinned scenario tree.",
  },
  {
    name: "build_tam",
    kind: "read",
    blurb: "What-if sizing: swap a value or re-point an input. Never persisted.",
  },
  {
    name: "resolve_market",
    kind: "read",
    blurb: "Free-form query → sourced TAM (registry-first, no LLM guessing).",
  },
  {
    name: "list_connectors",
    kind: "read",
    blurb: "The typed connectors behind the bank — connector, tier, methods.",
  },
  {
    name: "get_connector_data",
    kind: "live",
    blurb: "Pull a fresh number from a live API. Gated by STRATA_MCP_LIVE_CONNECTORS.",
  },
  {
    name: "import_portfolio",
    kind: "write",
    blurb: "Link portfolio companies to your org (idempotent on domain).",
  },
  {
    name: "size_company",
    kind: "write",
    blurb: "Size one linked company, registry-first and offline-safe.",
  },
  { name: "list_portfolio", kind: "read", blurb: "List linked companies with TAM + progress." },
];

const KIND_LABEL: Record<ToolKind, string> = {
  read: "Read",
  write: "Write",
  live: "Live",
};

const KIND_CLASS: Record<ToolKind, string> = {
  read: "bg-[var(--accent-soft)] text-[var(--accent)]",
  write: "bg-[var(--warn-soft,#3a2a12)] text-[var(--warn,#e0a44a)]",
  live: "bg-[var(--ok-soft,#13301f)] text-[var(--ok,#5fbf85)]",
};

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-[10px] border border-[var(--border-1)] bg-[var(--bg-0)] p-4 text-[12.5px] leading-[1.6] text-[var(--fg-2)]">
      <code>{children}</code>
    </pre>
  );
}

export default function AgentsPage() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-10 px-8 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="display text-[34px] leading-[1.05] text-[var(--fg-1)]">Agent harness</h1>
        <p className="max-w-[680px] text-[14px] text-[var(--fg-3)]">
          Strata is a research harness for your AI agents. The{" "}
          <span className="text-[var(--fg-1)]">Model Context Protocol</span> server exposes the data
          bank, frameworks, and live connectors as callable tools — so an agent sizes markets off{" "}
          <span className="text-[var(--fg-1)]">sourced, hash-pinned numbers</span> instead of
          guessing. Every numeric payload carries its <code>source_url</code>, tier, and{" "}
          <code>snapshot_sha256</code>.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-[13px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          How an agent uses it
        </h2>
        <div className="rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
          <pre className="overflow-x-auto text-[12.5px] leading-[1.7] text-[var(--fg-2)]">
            {`  agent question  ─▶  search_concepts / resolve_market   (find the market)
                  ─▶  list_frameworks                     (pick the recipe)
                  ─▶  size_tam / build_tam                (sourced scenario tree)
                  └▶  get_connector_data                  (pull a fresh number, live)
                           every result: value + unit + source_url + sha256`}
          </pre>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="display text-[20px] text-[var(--fg-1)]">Tools</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {TOOLS.map((t) => (
            <div
              key={t.name}
              className="flex flex-col gap-2 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <code className="text-[13px] text-[var(--fg-1)]">{t.name}</code>
                <span
                  className={`rounded-[6px] px-2 py-0.5 text-[10px] uppercase tracking-[0.06em] ${KIND_CLASS[t.kind]}`}
                >
                  {KIND_LABEL[t.kind]}
                </span>
              </div>
              <p className="text-[12.5px] text-[var(--fg-3)]">{t.blurb}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="display text-[20px] text-[var(--fg-1)]">Connect</h2>
        <p className="max-w-[680px] text-[14px] text-[var(--fg-3)]">
          The server speaks MCP over stdio (local agents) or streamable HTTP (hosted). Point any
          MCP-capable client — Claude Desktop, Claude Code, or your own agent — at it.
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="flex flex-col gap-2">
            <h3 className="text-[13px] text-[var(--fg-2)]">Local (stdio)</h3>
            <CodeBlock>{`{
  "mcpServers": {
    "strata": { "command": "strata-mcp" }
  }
}`}</CodeBlock>
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="text-[13px] text-[var(--fg-2)]">Hosted (HTTP)</h3>
            <CodeBlock>{`# streamable-HTTP endpoint
POST  https://<your-strata-host>/mcp

# enable live connector fetches (off by default)
STRATA_MCP_LIVE_CONNECTORS=1`}</CodeBlock>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="display text-[20px] text-[var(--fg-1)]">Frameworks are harnesses</h2>
        <p className="max-w-[680px] text-[14px] text-[var(--fg-3)]">
          A framework is a parameterized recipe (e.g. <code>persona_pool × cost_per_persona</code>)
          whose every input is a citable primitive. An agent picks a framework, binds inputs to
          sourced primitives via <code>build_tam</code>, and gets a defensible TAM it can show its
          work for — no fabricated figures, every number traceable to a snapshot.
        </p>
      </section>
    </main>
  );
}
