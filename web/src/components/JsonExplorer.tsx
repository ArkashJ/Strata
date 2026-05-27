"use client";

import { useState } from "react";

interface Props {
  data: unknown;
}

export function JsonExplorer({ data }: Props) {
  return (
    <div className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
      <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-4">Raw build response</h2>
      <div className="font-mono text-[12px] leading-[1.6]">
        <JsonNode value={data} depth={0} path="root" />
      </div>
    </div>
  );
}

function JsonNode({ value, depth, path }: { value: unknown; depth: number; path: string }) {
  const [collapsed, setCollapsed] = useState(depth > 1);
  const indent = depth * 16;

  if (value === null) {
    return <span className="text-[var(--fg-4)]">null</span>;
  }

  if (typeof value === "boolean") {
    return <span className="text-[var(--accent)]">{String(value)}</span>;
  }

  if (typeof value === "number") {
    return <span className="text-[#3fa66b]">{value.toLocaleString()}</span>;
  }

  if (typeof value === "string") {
    return <span className="text-[#c99846]">&quot;{value}&quot;</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[var(--fg-3)]">[]</span>;
    return (
      <span>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          {collapsed ? "▸" : "▾"} [{value.length}]
        </button>
        {!collapsed && (
          <div style={{ paddingLeft: indent > 0 ? 16 : 0 }}>
            {value.map((item, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: JSON array explorer, index is the label
              <div key={`${path}-${i}`} className="flex">
                <span className="text-[var(--fg-4)] select-none mr-2">{i}:</span>
                <JsonNode value={item} depth={depth + 1} path={`${path}[${i}]`} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-[var(--fg-3)]">{"{}"}</span>;
    return (
      <span>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          {collapsed ? "▸" : "▾"} {"{"}
          {collapsed && <span className="text-[var(--fg-4)]">{entries.length} keys</span>}
          {collapsed && "}"}
        </button>
        {!collapsed && (
          <div style={{ paddingLeft: indent > 0 ? 16 : 0 }}>
            {entries.map(([key, val]) => (
              <div key={`${path}.${key}`} className="flex">
                <span className="text-[var(--accent)] select-none mr-1">{key}:</span>
                <JsonNode value={val} depth={depth + 1} path={`${path}.${key}`} />
              </div>
            ))}
            <span className="text-[var(--fg-3)]">{"}"}</span>
          </div>
        )}
      </span>
    );
  }

  return <span className="text-[var(--fg-3)]">{String(value)}</span>;
}
