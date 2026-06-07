"""Tests for the static (HTML/PDF/SVG) report renderers + the export_report tool.

All pure / offline — no network, no LLM. The PDF path is skipped cleanly when
WeasyPrint's native libraries are unavailable (the dependency-graceful contract),
so this suite is green on a machine with or without the system libs.
"""

from __future__ import annotations

import asyncio

import pytest

from strata.evaluator import size_concept
from strata.mcp.server import load_registry
from strata.mcp.tools import export_report
from strata.report import (
    Branding,
    assemble_premium_report_for_tam,
    render_premium_html,
)
from strata.report.render_pdf import PdfUnavailableError, render_premium_pdf
from strata.report.svg_charts import BarChart, BarRow, render_bar_chart, render_ranked_bar_chart

_CONCEPT = "doc-gen-pc-insurance"


@pytest.fixture
def reg():
    return load_registry()


# --- svg_charts: pure builders ---------------------------------------------


def test_bar_chart_renders_labels_axis_and_source() -> None:
    chart = BarChart(
        title="Market size",
        subtitle="3 method families",
        source="Strata curated bank",
        rows=(
            BarRow(label="Lower", value=100.0, display="$100"),
            BarRow(label="Upper", value=300.0, display="$300"),
        ),
    )
    svg = render_bar_chart(chart)
    assert svg.startswith("<svg")
    assert "Market size" in svg
    assert "Lower" in svg and "Upper" in svg
    # Value labels are rendered verbatim from the (already-formatted) display.
    assert "$100" in svg and "$300" in svg
    # A baseline axis hairline + the source footnote are both present.
    assert "<line" in svg
    assert "Source: Strata curated bank" in svg


def test_bar_chart_empty_is_honest_not_fabricated() -> None:
    svg = render_bar_chart(BarChart(title="Competitive landscape", rows=(), source="bank"))
    # No data → an explicit honest-gap panel, never a fake bar (Q20).
    assert "no data" in svg.lower() or "honest gap" in svg.lower()
    assert "<rect" not in svg  # no bars drawn


def test_ranked_bar_sorts_descending() -> None:
    chart = BarChart(
        title="Ranked",
        rows=(
            BarRow(label="small", value=1.0, display="1"),
            BarRow(label="big", value=9.0, display="9"),
        ),
    )
    svg = render_ranked_bar_chart(chart)
    # The leader's label text appears before the smaller one in document order.
    assert svg.index(">big<") < svg.index(">small<")


def test_svg_escapes_markup() -> None:
    svg = render_bar_chart(
        BarChart(title="A & B <x>", rows=(BarRow(label="<b>", value=1.0, display="1"),))
    )
    assert "&amp;" in svg and "&lt;" in svg
    assert "<x>" not in svg  # the literal angle brackets are escaped


# --- render_html ------------------------------------------------------------


def test_render_premium_html_contains_headline_svg_sources_limitations(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    pr = assemble_premium_report_for_tam(reg, tam)
    html = render_premium_html(pr)
    # A self-contained document (inline style, no external assets).
    assert html.startswith("<!doctype html>")
    assert "<style>" in html and "src=http" not in html
    # The editorial headline text (escaped) is present.
    assert pr.headline.replace("&", "&amp;") in html
    # At least one inline-SVG chart is rendered.
    assert "<svg" in html
    # The sources appendix table and the limitations section both render.
    assert 'class="sources"' in html
    assert "Limitations" in html


def test_render_premium_html_applies_branding(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    pr = assemble_premium_report_for_tam(reg, tam)
    html = render_premium_html(
        pr,
        Branding(
            firm_name="Altimeter Capital",
            prepared_by="Maya",
            brand_color="#123456",
            disclaimer="Confidential — internal use only.",
        ),
    )
    assert "Altimeter Capital" in html
    assert "Prepared by Maya" in html
    assert "#123456" in html  # the brand accent overrides the Strata indigo
    assert "Confidential" in html


# --- render_pdf: dependency-graceful ---------------------------------------


def test_render_pdf_graceful_or_bytes() -> None:
    html = "<!doctype html><html><body><p>hi</p></body></html>"
    try:
        out = render_premium_pdf(html)
    except PdfUnavailableError:
        pytest.skip("WeasyPrint native libs unavailable — graceful fallback path exercised")
    else:
        assert isinstance(out, bytes) and out[:4] == b"%PDF"


# --- export_report MCP tool ------------------------------------------------


def test_export_report_html_bundles_max_utility(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    reg.remember_tam(tam)
    out = asyncio.run(export_report(reg, state_hash=tam.state_hash, format="html"))
    assert out["state_hash"] == tam.state_hash
    assert out["format"] == "html"
    assert out["html"].startswith("<!doctype html>")
    assert out["pdf_base64"] is None and out["pdf_available"] is False
    # Maximum-utility bundle: structured premium + charts + citations + next_actions.
    assert out["premium"]["state_hash"] == tam.state_hash
    assert out["charts"]
    assert isinstance(out["citations"], list)
    assert out["next_actions"]


def test_export_report_pdf_path_skips_cleanly_when_unavailable(reg) -> None:
    tam = size_concept(reg, _CONCEPT)
    reg.remember_tam(tam)
    out = asyncio.run(export_report(reg, state_hash=tam.state_hash, format="pdf"))
    # Either WeasyPrint produced a PDF (base64 present) or it degraded to HTML with
    # an honest note — never an error, never a missing html field.
    assert out["html"].startswith("<!doctype html>")
    if out["pdf_available"]:
        assert out["pdf_base64"]
    else:
        assert out["pdf_base64"] is None
        assert "pdf_note" in out


def test_export_report_unknown_hash_raises(reg) -> None:
    from strata.mcp.errors import ToolError

    with pytest.raises(ToolError):
        asyncio.run(export_report(reg, state_hash="0" * 64))
