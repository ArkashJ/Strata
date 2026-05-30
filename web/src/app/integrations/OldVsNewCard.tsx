// Wave 5C / AC5C.3 — the "old way vs new way" comparison: a broken (red) pile of
// disconnected report PDFs vs the connected (green) Strata pipeline.
const OLD = ["$20k report", "stale PDF", "no sources", "no recompute"];
const NEW = ["live sources", "hash-pinned", "recompute", "your private data"];

export function OldVsNewCard() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div
        className="canvas-card flex flex-col gap-3 p-5"
        style={{ borderRadius: "var(--r-3)", boxShadow: "inset 0 0 0 1px #f8717155" }}
      >
        <div className="flex items-center gap-2 text-[13px] font-medium text-[#f87171]">
          <span className="text-[16px]">✕</span> The old way
        </div>
        <ul className="flex flex-col gap-1.5">
          {OLD.map((t) => (
            <li key={t} className="flex items-center gap-2 text-[13px] text-[var(--fg-2)]">
              <span className="text-[#f87171]">—</span>
              <span className="line-through opacity-70">{t}</span>
            </li>
          ))}
        </ul>
      </div>
      <div
        className="canvas-card flex flex-col gap-3 p-5"
        style={{ borderRadius: "var(--r-3)", boxShadow: "inset 0 0 0 1px #34d39955" }}
      >
        <div className="flex items-center gap-2 text-[13px] font-medium text-[#34d399]">
          <span className="text-[16px]">✓</span> The Strata way
        </div>
        <ul className="flex flex-col gap-1.5">
          {NEW.map((t) => (
            <li key={t} className="flex items-center gap-2 text-[13px] text-[var(--fg-1)]">
              <span className="text-[#34d399]">→</span>
              {t}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
