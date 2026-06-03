// Number-level provenance (sub-project 3): the displayed number ITSELF links to
// the source behind it — a reader can click any figure and land on the document
// it came from. Composites (and pre-enrichment payloads) carry no single
// source_url, so they render as a plain span: we never link a derived number to
// an invented URL.

import { formatCompact } from "@/lib/format";
import type { InputUsed } from "@/lib/schemas";

export function SourcedNumber({
  input,
  className = "",
}: {
  input: InputUsed;
  className?: string;
}) {
  if (input.value == null) return <span className={className}>—</span>;
  const text = formatCompact(input.value, input.unit ?? null);
  if (!input.source_url) {
    return <span className={`tabular-nums ${className}`}>{text}</span>;
  }
  return (
    <a
      href={input.source_url}
      target="_blank"
      rel="noopener noreferrer"
      title={`Source: ${input.source_url}`}
      data-testid="sourced-number"
      className={`tabular-nums underline decoration-dotted underline-offset-2 hover:text-[var(--accent)] ${className}`}
    >
      {text}
    </a>
  );
}
