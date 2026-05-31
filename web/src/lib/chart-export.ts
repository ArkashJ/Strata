// Client-side chart export (downloadable graphs). Recharts renders an inline
// <svg>; we serialize it to a standalone SVG or rasterize to PNG entirely in the
// browser — no server round-trip, no new data. The one subtlety: the live charts
// colour themselves with CSS custom properties (--accent, --fg-1, …) and Tailwind
// classes, none of which survive once the SVG is detached from the document. So we
// walk the clone and inline the *computed* paint/typography for every node, turning
// every var() reference into a concrete value that renders identically offline.

const INLINED_PROPS = [
  "fill",
  "fill-opacity",
  "stroke",
  "stroke-width",
  "stroke-opacity",
  "stroke-dasharray",
  "color",
  "opacity",
  "font-family",
  "font-size",
  "font-weight",
  "text-anchor",
] as const;

function inlineComputedStyles(source: SVGSVGElement, clone: SVGSVGElement): void {
  const sourceNodes = source.querySelectorAll<SVGElement>("*");
  const cloneNodes = clone.querySelectorAll<SVGElement>("*");
  // querySelectorAll returns nodes in identical document order for a structural
  // clone, so index alignment is safe.
  for (let i = 0; i < sourceNodes.length; i++) {
    const live = sourceNodes[i];
    const target = cloneNodes[i];
    if (!live || !target) continue;
    const computed = getComputedStyle(live);
    let inline = "";
    for (const prop of INLINED_PROPS) {
      const value = computed.getPropertyValue(prop);
      if (value && value !== "none" && value !== "normal") inline += `${prop}:${value};`;
    }
    if (inline) target.setAttribute("style", inline);
  }
}

function serialize(svg: SVGSVGElement): { xml: string; width: number; height: number } {
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width || svg.clientWidth || 640));
  const height = Math.max(1, Math.round(rect.height || svg.clientHeight || 360));

  const clone = svg.cloneNode(true) as SVGSVGElement;
  inlineComputedStyles(svg, clone);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  if (!clone.getAttribute("viewBox")) clone.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const xml = new XMLSerializer().serializeToString(clone);
  return { xml, width, height };
}

function triggerDownload(href: string, filename: string): void {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function downloadChartSvg(svg: SVGSVGElement, filename: string): void {
  const { xml } = serialize(svg);
  const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${xml}`], {
    type: "image/svg+xml;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename.endsWith(".svg") ? filename : `${filename}.svg`);
  // Defer revoke: the click navigates on a later microtask, so revoking
  // synchronously can cancel the download before it starts (empty file).
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Rasterize at 2× for crisp slides/memos. `background` paints behind the
// transparent chart so a dark-theme export isn't an invisible blob on white.
export async function downloadChartPng(
  svg: SVGSVGElement,
  filename: string,
  background = "#ffffff",
  scale = 2,
): Promise<void> {
  const { xml, width, height } = serialize(svg);
  const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;

  const image = new Image();
  image.width = width;
  image.height = height;
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("chart image failed to load"));
    image.src = svgUrl;
  });

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas 2d context unavailable");
  ctx.scale(scale, scale);
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("canvas toBlob returned null");
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename.endsWith(".png") ? filename : `${filename}.png`);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Resolve a themed CSS custom property to a concrete colour for the PNG backdrop.
export function resolveCssVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}
