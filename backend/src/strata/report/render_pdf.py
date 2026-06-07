"""Render the self-contained HTML deck to a PDF via WeasyPrint — dependency-graceful.

WeasyPrint turns the inline-SVG/CSS HTML (``render_html.render_premium_html``)
into a print-faithful PDF with no browser. But WeasyPrint depends on system
libraries (pango, cairo, gobject) that are not always present, so this module
fails **loud and clear**: if WeasyPrint or its native libs are missing,
:func:`render_premium_pdf` raises :class:`PdfUnavailableError` so callers (the CLI
``--pdf`` flag, the MCP ``export_report`` tool) can fall back to HTML cleanly
rather than crash.

The import is attempted lazily at call time (not module import) because the
``weasyprint`` Python package imports fine even when the native libs are absent —
the failure only surfaces on the first render call.
"""

from __future__ import annotations


class PdfUnavailableError(RuntimeError):
    """WeasyPrint (or its native libs) is unavailable, so no PDF can be produced.

    Carries an actionable message so the caller can fall back to HTML and tell the
    user how to enable PDF (install the WeasyPrint system dependencies).
    """


_INSTALL_HINT = (
    "PDF export needs WeasyPrint and its native libraries (pango, cairo, gobject). "
    "Install them (e.g. `brew install pango` on macOS, `apt-get install "
    "libpango-1.0-0 libpangocairo-1.0-0` on Debian) — see "
    "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation"
)


def render_premium_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes via WeasyPrint.

    Raises :class:`PdfUnavailableError` (never a raw ``ImportError`` / ``OSError``)
    when WeasyPrint or its native libraries cannot be loaded, so the caller can
    fall back to the HTML deliverable. Any other render error propagates as-is.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except Exception as exc:  # ImportError, or OSError from a half-installed lib
        raise PdfUnavailableError(_INSTALL_HINT) from exc

    try:
        pdf = HTML(string=html).write_pdf()
    except OSError as exc:
        # The native libs load lazily on the first render call, so a missing
        # libgobject surfaces here as an OSError — translate to the clear signal.
        raise PdfUnavailableError(_INSTALL_HINT) from exc

    if pdf is None:  # pragma: no cover - write_pdf(target=None) returns bytes
        raise PdfUnavailableError("WeasyPrint returned no PDF bytes.")
    return pdf


__all__ = ["PdfUnavailableError", "render_premium_pdf"]
