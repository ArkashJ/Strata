/**
 * My Bank — the personal tier. Stub so the sidebar link resolves; the real
 * surface (synced primitives, saved builds/graphs/TAMs/macros) lands later.
 */

export default function BankPage() {
  return (
    <main className="flex flex-1 flex-col">
      <header className="px-8 pt-7 pb-6 border-b border-[var(--border-1)]">
        <h1 className="display text-[26px] leading-tight text-[var(--fg-1)] text-balance">
          My Bank
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[14px] text-[var(--fg-2)]">
          Your private primitives, builds, graphs, TAMs, and macros — synced via the CLI/MCP.
        </p>
      </header>
      {/* TODO(bank-agent): real content */}
    </main>
  );
}
