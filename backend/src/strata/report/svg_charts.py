"""Pure inline-SVG chart builders for the static (HTML/PDF) report deck.

These render server-side, with **no browser and no third-party deps** — just
string assembly — so a `PremiumReport` can be turned into a self-contained
deliverable (HTML or weasyprint PDF) that an analyst forwards. The Vega-Lite /
Mermaid specs in ``mcp/charts.py`` cover *interactive* hosts; these cover the
*frozen* deliverable where nothing executes.

Every builder is pure and typed. None of them invent a number: each takes already
-computed ``(label, value)`` rows off the report and lays them out. A chart with
no rows returns an honest "no data yet" placeholder, never a fabricated shape.

Visual contract mirrors the Altimeter/Coatue deck (``docs/design/todos/``):
editorial title + subtitle, a single accent ink, an axis baseline, value labels
on each bar, tabular-mono numerals, and a source footnote line under every chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Strata brand palette (verbatim from docs/design/brand-kit.md). The static deck
# is light-default: deep ink type on paper, one indigo accent voice.
INK = "#0A0A0B"
FG_2 = "#52525B"
FG_3 = "#7E7E86"
ACCENT = "#5B5BD6"
ACCENT_SOFT = "#C9C9F0"
BORDER = "#E8E8EC"
PAPER = "#FFFFFF"

_MONO = "'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace"
_SANS = "'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif"


@dataclass(frozen=True, slots=True)
class BarRow:
    """One labelled datum on a bar chart: a category label and a numeric value,
    plus an already-formatted display string (the report formats figures itself,
    so the chart never re-derives or invents a number)."""

    label: str
    value: float
    display: str


@dataclass(frozen=True, slots=True)
class BarChart:
    """A labelled bar chart spec: editorial title + subtitle, the rows, and the
    source footnote line that rides under every chart in the deck."""

    title: str
    rows: tuple[BarRow, ...]
    subtitle: str = ""
    source: str = ""
    ranked: bool = False
    width: int = 720
    bar_height: int = 34
    extra_classes: tuple[str, ...] = field(default_factory=tuple)


def _esc(text: str) -> str:
    """Minimal XML escaping for text that lands inside SVG <text> nodes."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _empty_chart(title: str, subtitle: str, source: str, width: int) -> str:
    """Honest "no data yet" panel — used whenever a section has no sourced rows.

    Renders the headline + an explicit gap note rather than an empty axis, so the
    deliverable never shows a chart frame that implies data we do not have (Q20).
    """
    note = "No sourced data for this chart yet — an honest gap, not a fabricated series."
    parts = [
        f'<svg class="strata-chart strata-chart--empty" width="{width}" height="120" '
        f'viewBox="0 0 {width} 120" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="{_esc(title)} (no data)">',
        f'<text x="0" y="20" font-family="{_SANS}" font-size="15" font-weight="700" '
        f'fill="{INK}">{_esc(title)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="0" y="40" font-family="{_SANS}" font-size="12" fill="{FG_2}">'
            f"{_esc(subtitle)}</text>"
        )
    parts.append(
        f'<text x="0" y="74" font-family="{_SANS}" font-size="13" fill="{FG_3}" '
        f'font-style="italic">{_esc(note)}</text>'
    )
    if source:
        parts.append(
            f'<text x="0" y="108" font-family="{_SANS}" font-size="10.5" fill="{FG_3}">'
            f"{_esc('Source: ' + source)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def render_bar_chart(chart: BarChart) -> str:
    """Render a labelled horizontal bar chart as a self-contained inline SVG.

    Layout: title + subtitle band on top, one row per datum (category label,
    accent bar scaled to the max value, value label at the bar end), a baseline
    axis on the left, and the source footnote underneath. The ``ranked`` variant
    sorts rows descending and tints the leading bar a stronger accent — the
    Altimeter "ranked distribution" look. Pure string assembly; no escaping gaps.
    """
    rows = chart.rows
    if not rows:
        return _empty_chart(chart.title, chart.subtitle, chart.source, chart.width)

    ordered = (
        tuple(sorted(rows, key=lambda r: abs(r.value), reverse=True)) if chart.ranked else rows
    )
    max_value = max((abs(r.value) for r in ordered), default=0.0) or 1.0

    pad_left = 220  # room for category labels
    pad_right = 96  # room for the value label past the bar end
    pad_top = 52 if chart.subtitle else 36
    pad_bottom = 40 if chart.source else 16
    plot_width = max(chart.width - pad_left - pad_right, 80)
    gap = 12
    height = pad_top + len(ordered) * (chart.bar_height + gap) + pad_bottom

    parts: list[str] = [
        f'<svg class="strata-chart" width="{chart.width}" height="{height}" '
        f'viewBox="0 0 {chart.width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="{_esc(chart.title)}">',
        f'<text x="0" y="20" font-family="{_SANS}" font-size="15" font-weight="700" '
        f'fill="{INK}">{_esc(chart.title)}</text>',
    ]
    if chart.subtitle:
        parts.append(
            f'<text x="0" y="40" font-family="{_SANS}" font-size="12" fill="{FG_2}">'
            f"{_esc(chart.subtitle)}</text>"
        )

    # The axis baseline (a single vertical hairline at the bars' left edge).
    axis_top = pad_top - 6
    axis_bottom = pad_top + len(ordered) * (chart.bar_height + gap) - gap
    parts.append(
        f'<line x1="{pad_left}" y1="{axis_top}" x2="{pad_left}" y2="{axis_bottom}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
    )

    for i, row in enumerate(ordered):
        y = pad_top + i * (chart.bar_height + gap)
        bar_w = max(int(plot_width * (abs(row.value) / max_value)), 2)
        fill = ACCENT if (not chart.ranked or i == 0) else ACCENT_SOFT
        text_mid = y + chart.bar_height / 2 + 4
        parts.append(
            f'<text x="{pad_left - 12}" y="{text_mid:.0f}" text-anchor="end" '
            f'font-family="{_SANS}" font-size="12.5" fill="{FG_2}">{_esc(row.label)}</text>'
        )
        parts.append(
            f'<rect x="{pad_left}" y="{y}" width="{bar_w}" height="{chart.bar_height}" '
            f'rx="3" fill="{fill}"/>'
        )
        parts.append(
            f'<text x="{pad_left + bar_w + 8}" y="{text_mid:.0f}" '
            f'font-family="{_MONO}" font-size="12.5" font-weight="600" fill="{INK}">'
            f"{_esc(row.display)}</text>"
        )

    if chart.source:
        parts.append(
            f'<text x="0" y="{height - 12}" font-family="{_SANS}" font-size="10.5" '
            f'fill="{FG_3}">{_esc("Source: " + chart.source)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_ranked_bar_chart(chart: BarChart) -> str:
    """Convenience wrapper that forces the ranked (sorted, leader-tinted) variant.

    Uses ``dataclasses.replace`` so every field (incl. any added later) is carried
    over — only ``ranked`` is flipped (review #129)."""
    return render_bar_chart(replace(chart, ranked=True))


__all__ = [
    "ACCENT",
    "INK",
    "BarChart",
    "BarRow",
    "render_bar_chart",
    "render_ranked_bar_chart",
]
