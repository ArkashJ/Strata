"""Render a :class:`PremiumReport` into a self-contained Altimeter-grade HTML deck.

The output is one HTML document with an inline ``<style>`` block and inline-SVG
charts — **no external assets, no JS, no web fonts fetched at render time** — so
it is a forwardable, frozen deliverable an analyst can email or print to PDF
(``render_pdf.render_premium_pdf``). The visual register follows the deck refs in
``docs/design/todos/``: bold editorial section headline + subtitle, generous
whitespace, light paper, tabular-mono numerals, a source footnote on every chart.

This layer is **rendering only**: every figure already lives on the
``PremiumReport`` (sourced or reproducibly derived, Q20-fenced upstream). A
section with no sourced answers renders honest "no data yet" copy, never a
fabricated chart.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..models.question import AnswerProvenance, ResolvedAnswer
from .narrative import usd
from .sections import PremiumReport, ReportSection
from .svg_charts import ACCENT, INK, BarChart, BarRow, render_bar_chart


class Branding(BaseModel):
    """Optional firm branding applied to the report header + footer.

    All fields are optional — an unbranded report renders the Strata default
    chrome. ``logo_data_uri`` is preferred for a frozen deliverable (it embeds the
    image so the HTML stays self-contained); ``logo_url`` is a fallback that
    references an external asset (resolved by the viewer, not at render time).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    firm_name: str | None = None
    prepared_by: str | None = None
    logo_url: str | None = None
    logo_data_uri: str | None = None
    brand_color: str | None = None
    disclaimer: str | None = None


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _accent(branding: Branding | None) -> str:
    """The accent ink: a firm's brand color when branded, else Strata indigo."""
    if branding is not None and branding.brand_color:
        return branding.brand_color
    return ACCENT


# Which premium sections get a chart, and the row source for each. The market-size
# section reads scenario rows off the report range; the rest read the section's
# own sourced answers. A section absent here renders prose only.
def _answer_rows(answers: tuple[ResolvedAnswer, ...]) -> tuple[BarRow, ...]:
    """Turn answered, numeric rows into chart data — sourced display values only."""
    rows: list[BarRow] = []
    for a in answers:
        if a.status == "answered" and a.value is not None:
            label = a.prompt if len(a.prompt) <= 48 else a.prompt[:45] + "…"
            rows.append(BarRow(label=label, value=a.value, display=a.display or usd(a.value)))
    return tuple(rows)


def _market_size_chart(pr: PremiumReport) -> str:
    """The headline range as a 3-bar chart (low / mid / high) — the deck's lede."""
    if pr.range_mid is None or pr.range_low is None or pr.range_high is None:
        return render_bar_chart(
            BarChart(
                title="Market size",
                rows=(),
                subtitle="Unsizable from the curated bank",
                source="Strata curated bank",
            )
        )
    rows = (
        BarRow(label="Lower bound", value=pr.range_low, display=usd(pr.range_low)),
        BarRow(label="Triangulated midpoint", value=pr.range_mid, display=usd(pr.range_mid)),
        BarRow(label="Upper bound", value=pr.range_high, display=usd(pr.range_high)),
    )
    return render_bar_chart(
        BarChart(
            title="Market size — defensible range",
            rows=rows,
            subtitle=f"{len(pr.method_families)} method families · independence "
            f"{pr.independence_score:.2f}",
            source="Strata triangulated scenarios (hash-pinned)",
        )
    )


def _section_chart(section: ReportSection, pr: PremiumReport) -> str | None:
    """The inline-SVG chart for a section, or ``None`` when it carries prose only."""
    if section.key == "market_size":
        return _market_size_chart(pr)
    if section.chart is None:
        return None
    rows = _answer_rows(section.answers)
    ranked = section.chart in {"ranked_bar", "tornado"}
    return render_bar_chart(
        BarChart(
            title=section.title,
            rows=rows,
            subtitle="" if rows else "No sourced data for this section yet",
            source="Strata curated bank",
            ranked=ranked,
        )
    )


def _kpi_strip(pr: PremiumReport) -> str:
    """The top KPI strip: range low / mid / high + independence + method families."""
    cells: list[tuple[str, str]] = []
    if pr.range_low is not None:
        cells.append(("Lower bound", usd(pr.range_low)))
    if pr.range_mid is not None:
        cells.append(("Triangulated", usd(pr.range_mid)))
    if pr.range_high is not None:
        cells.append(("Upper bound", usd(pr.range_high)))
    cells.append(("Independence", f"{pr.independence_score:.2f}"))
    cells.append(("Method families", str(len(pr.method_families))))
    if pr.spread_x is not None:
        cells.append(("Spread", f"{pr.spread_x:.1f}×"))
    items = "".join(
        f'<div class="kpi"><div class="kpi-label">{_esc(label)}</div>'
        f'<div class="kpi-value">{_esc(value)}</div></div>'
        for label, value in cells
    )
    return f'<div class="kpi-strip">{items}</div>'


def _sources_table(sources: tuple[AnswerProvenance, ...]) -> str:
    """The sources appendix: one row per cited primitive (slug · tier · url · snapshot)."""
    if not sources:
        return '<p class="muted">No sourced primitives backed this report.</p>'
    rows = []
    for s in sources:
        url = (
            f'<a href="{_esc(s.source_url)}">{_esc(s.source_url)}</a>'
            if s.source_url
            else '<span class="muted">— (modeled / composite)</span>'
        )
        tier = _esc(s.source_tier or "—")
        snap = _esc((s.snapshot_sha256 or "")[:16] + "…") if s.snapshot_sha256 else "—"
        rows.append(
            f"<tr><td>{_esc(s.primitive_slug)}</td><td>{tier}</td>"
            f"<td>{url}</td><td class='mono'>{snap}</td></tr>"
        )
    body = "".join(rows)
    return (
        '<table class="sources"><thead><tr><th>Primitive</th><th>Tier</th>'
        f"<th>Source</th><th>Snapshot</th></tr></thead><tbody>{body}</tbody></table>"
    )


def _limitations(limitations: tuple[str, ...]) -> str:
    if not limitations:
        return '<p class="muted">No modeled inputs or scope divergences flagged.</p>'
    items = "".join(f"<li>{_esc(text)}</li>" for text in limitations)
    return f"<ul class='limitations'>{items}</ul>"


def _branding_header(branding: Branding | None) -> str:
    if branding is None or not (branding.firm_name or branding.logo_data_uri or branding.logo_url):
        return ""
    logo = ""
    src = branding.logo_data_uri or branding.logo_url
    if src:
        logo = f'<img class="brand-logo" src="{_esc(src)}" alt="logo"/>'
    firm = (
        f'<span class="brand-firm">{_esc(branding.firm_name)}</span>' if branding.firm_name else ""
    )
    prep = (
        f'<span class="brand-prep">Prepared by {_esc(branding.prepared_by)}</span>'
        if branding.prepared_by
        else ""
    )
    return f'<header class="brand-header">{logo}{firm}{prep}</header>'


def _branding_footer(branding: Branding | None) -> str:
    disclaimer = branding.disclaimer if branding is not None else None
    default = (
        "Generated by Strata — every figure traces to a sourced primitive or a "
        "reproducible derivation at this TAM's permalink."
    )
    text = disclaimer or default
    return f'<footer class="brand-footer">{_esc(text)}</footer>'


def _style(accent: str) -> str:
    """The inline stylesheet — light paper, editorial type, tabular-mono numerals."""
    return f"""
    :root {{ --accent: {accent}; --ink: {INK}; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: #FAFAFA; color: var(--ink);
      font-family: 'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif;
      font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased;
    }}
    .page {{ max-width: 880px; margin: 0 auto; padding: 56px 48px 72px; background: #FFFFFF; }}
    .mono, .kpi-value, td.mono {{
      font-family: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;
      font-variant-numeric: tabular-nums;
    }}
    .headline {{ font-size: 34px; line-height: 1.12; font-weight: 700; letter-spacing: -0.01em;
      margin: 0 0 8px; }}
    .subtitle {{ font-size: 15px; color: #52525B; margin: 0 0 32px; }}
    h2 {{ font-size: 21px; font-weight: 700; letter-spacing: -0.01em; margin: 44px 0 6px;
      padding-top: 28px; border-top: 1px solid #E8E8EC; }}
    h2:first-of-type {{ border-top: none; padding-top: 0; }}
    .section-body {{ color: #27272A; margin: 0 0 14px; }}
    .muted {{ color: #7E7E86; }}
    .gap {{ color: #7E7E86; font-style: italic; }}
    .kpi-strip {{ display: flex; flex-wrap: wrap; gap: 28px; padding: 22px 0 8px;
      margin-bottom: 28px; border-bottom: 1px solid #E8E8EC; }}
    .kpi-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
      color: #7E7E86; }}
    .kpi-value {{ font-size: 24px; font-weight: 700; color: var(--ink); }}
    .strata-chart {{ display: block; margin: 16px 0 8px; max-width: 100%; }}
    table.sources {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }}
    table.sources th {{ text-align: left; color: #52525B; font-weight: 600; padding: 7px 10px;
      border-bottom: 1px solid #D4D4D8; font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.04em; }}
    table.sources td {{ padding: 7px 10px; border-bottom: 1px solid #F0F0F2; vertical-align: top; }}
    table.sources tr:nth-child(even) td {{ background: #FAFAFA; }}
    a {{ color: var(--accent); text-decoration: none; }}
    ul.limitations {{ margin: 8px 0; padding-left: 20px; }}
    ul.limitations li {{ margin: 4px 0; color: #27272A; }}
    .brand-header {{ display: flex; align-items: center; gap: 16px; padding-bottom: 18px;
      margin-bottom: 28px; border-bottom: 2px solid var(--accent); }}
    .brand-logo {{ height: 34px; width: auto; }}
    .brand-firm {{ font-weight: 700; font-size: 17px; }}
    .brand-prep {{ margin-left: auto; color: #7E7E86; font-size: 13px; }}
    .brand-footer {{ margin-top: 48px; padding-top: 18px; border-top: 1px solid #E8E8EC;
      color: #7E7E86; font-size: 12px; }}
    @media print {{ body {{ background: #FFFFFF; }} .page {{ padding: 0; }}
      h2 {{ break-after: avoid; }} .strata-chart {{ break-inside: avoid; }} }}
    """


def render_premium_html(pr: PremiumReport, branding: Branding | None = None) -> str:
    """Render the premium report into a single self-contained HTML deck.

    Section order matches the $1M-report anatomy: KPI strip → executive summary →
    market definition & scope → market size → triangulation → segmentation →
    competitive landscape → growth drivers → unit economics → regulation & risks →
    sources appendix → limitations. Charts are inline SVG; gaps render honest
    "no data yet" copy.
    """
    accent = _accent(branding)
    body: list[str] = [
        _branding_header(branding),
        f'<h1 class="headline">{_esc(pr.headline)}</h1>',
        f'<p class="subtitle">{_esc(pr.subtitle)}</p>',
        _kpi_strip(pr),
    ]

    for section in pr.sections:
        body.append(f"<h2>{_esc(section.title)}</h2>")
        summary_class = "section-body gap" if section.is_gap else "section-body"
        body.append(f'<p class="{summary_class}">{_esc(section.summary)}</p>')
        chart = _section_chart(section, pr)
        if chart is not None:
            body.append(chart)

    body.append("<h2>Sources &amp; provenance appendix</h2>")
    body.append(
        '<p class="section-body">Every figure above traces to one of the primitives '
        "below — named, tiered, and content-hash pinned for reproducibility.</p>"
    )
    body.append(_sources_table(pr.sources))

    body.append("<h2>Limitations &amp; caveats</h2>")
    body.append(
        '<p class="section-body">Honest about limits: modeled inputs and scope '
        "divergences are surfaced here, never hidden.</p>"
    )
    body.append(_limitations(pr.limitations))
    body.append(_branding_footer(branding))

    inner = "\n".join(p for p in body if p)
    title = _esc(f"{pr.concept_name} — market report")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title}</title><style>{_style(accent)}</style></head>"
        f'<body><main class="page">{inner}</main></body></html>'
    )


__all__ = ["Branding", "render_premium_html"]
