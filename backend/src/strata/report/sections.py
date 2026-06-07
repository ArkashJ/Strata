"""Premium report anatomy (P4): the MBB/CDD/IBISWorld section skeleton.

Composes the already-resolved, Q20-fenced :class:`ResolvedAnswer` rows + the
sourced :class:`TAMOutput` into the section structure a $1M market report
carries — executive summary, market definition, triangulation, segmentation,
competitive landscape, growth drivers, sensitivity, sources appendix,
limitations. This layer adds **structure and rendering only**: it never produces
a new number. Every figure still comes off a sourced primitive or a reproducible
TAM derivation, and a section with no sourced answers is an honest gap, not filler.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..models.question import AnswerProvenance, QuestionCategory, ResolvedAnswer
from ..models.tam_output import TAMOutput
from ..registry import Registry
from .assembler import MarketReport, assemble_report_for_tam
from .narrative import executive_summary, triangulation_note, usd

# Premium section -> which question categories feed it. Order is the report's
# reading order (answer-first pyramid: headline, then evidence, then caveats).
_SECTION_CATEGORIES: tuple[tuple[str, str, tuple[QuestionCategory, ...]], ...] = (
    ("market_size", "Market size", (QuestionCategory.MARKET_SIZE,)),
    ("triangulation", "Triangulation & methodology", (QuestionCategory.METHODOLOGY,)),
    (
        "segmentation",
        "Segmentation & geography",
        (QuestionCategory.SEGMENTATION, QuestionCategory.GEOGRAPHY),
    ),
    ("competitive_landscape", "Competitive landscape", (QuestionCategory.COMPETITION_SHARE,)),
    (
        "growth_drivers",
        "Growth & adoption drivers",
        (QuestionCategory.GROWTH_RATE, QuestionCategory.ADOPTION),
    ),
    ("unit_economics", "Unit economics", (QuestionCategory.UNIT_ECONOMICS,)),
    (
        "regulation_risks",
        "Regulation & risks",
        (QuestionCategory.REGULATION, QuestionCategory.RISKS),
    ),
)

# A chart hint per section the web maps to a component (Coatue/Gartner archetypes).
_SECTION_CHART: dict[str, str] = {
    "market_size": "composition",
    "triangulation": "scenario_comparison",
    "growth_drivers": "tornado",
    "segmentation": "ranked_bar",
    "competitive_landscape": "quadrant",
}


class ReportSection(BaseModel):
    """One section of the premium report: a heading, a token-fenced summary, the
    sourced answer rows behind it, and an optional chart hint for the web."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    title: str
    summary: str
    chart: str | None = None
    answers: tuple[ResolvedAnswer, ...] = ()
    is_gap: bool = False


class PremiumReport(BaseModel):
    """The $1M-report view: editorial headline + sourced range + sections +
    a deduped sources appendix + honest limitations. Additive over
    :class:`MarketReport` — same fence, richer structure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept_slug: str
    concept_name: str
    state_hash: str | None = None
    headline: str
    subtitle: str
    range_low: float | None = None
    range_mid: float | None = None
    range_high: float | None = None
    spread_x: float | None = None
    independence_score: float = 0.0
    method_families: tuple[str, ...] = ()
    sections: tuple[ReportSection, ...] = ()
    sources: tuple[AnswerProvenance, ...] = ()
    limitations: tuple[str, ...] = Field(default=())


def _scenario_values(tam: TAMOutput) -> list[float]:
    return [s.value for s in tam.scenarios]


def _range(tam: TAMOutput | None) -> tuple[float | None, float | None, float | None]:
    if tam is None:
        return None, None, None
    vals = _scenario_values(tam)
    if not vals:
        return None, None, None
    low, high = min(vals), max(vals)
    return low, (low + high) / 2.0, high


def _dedup_sources(answers: tuple[ResolvedAnswer, ...]) -> tuple[AnswerProvenance, ...]:
    """One row per primitive across the whole report (the bibliography)."""
    seen: dict[str, AnswerProvenance] = {}
    for a in answers:
        for p in a.provenance:
            seen.setdefault(p.primitive_slug, p)
    return tuple(sorted(seen.values(), key=lambda p: p.primitive_slug))


def _limitations(tam: TAMOutput | None) -> tuple[str, ...]:
    """Honest caveats: modeled inputs and scope divergences — never hidden."""
    if tam is None:
        return ("Market is unsizable from the curated bank; figures are gaps, not estimates.",)
    out: list[str] = []
    seen_banners: set[str] = set()
    for s in tam.scenarios:
        for b in s.banners:
            msg = getattr(b, "message", None) or getattr(b, "kind", None)
            if msg and str(msg) not in seen_banners:
                seen_banners.add(str(msg))
                out.append(str(msg))
    scope = getattr(tam, "scope", None)
    warnings = getattr(scope, "warnings", ()) if scope is not None else ()
    for w in warnings:
        text = getattr(w, "message", None) or str(w)
        out.append(str(text))
    return tuple(out)


def _scope_summary(tam: TAMOutput | None) -> str:
    """Whether the sourced inputs actually cover the declared market (snap-to-truth).

    A clean scope is a credibility signal; a divergence is *why* methods disagree —
    surfaced, not hidden. Reads the attached ScopeReport defensively (it is optional)."""
    if tam is None:
        return "Market is unsizable from the curated bank, so its scope is undefined here."
    scope = getattr(tam, "scope", None)
    if scope is None:
        return (
            "This concept does not declare a structured market scope (vertical / persona / "
            "segment / geo) yet — the figures are not scope-checked against a declared market."
        )
    if getattr(scope, "ok", False):
        return (
            "The sourced primitives' actual scope matches the declared market across every "
            "checked dimension — no narrowing or broadening that would misrepresent the size."
        )
    return (
        "Some sourced inputs are narrower or broader than the declared market (see the scope "
        "check). The displayed scope snaps to the primitives' truth, and the divergence is the "
        "leading explanation for any disagreement between methods — surfaced, not hidden."
    )


def build_premium_report(tam: TAMOutput | None, base: MarketReport) -> PremiumReport:
    """Group the fenced answers into the premium section skeleton + render
    token-fenced prose from the TAM's own figures."""
    by_category: dict[QuestionCategory, list[ResolvedAnswer]] = {}
    for a in base.answers:
        by_category.setdefault(a.category, []).append(a)

    low, mid, high = _range(tam)
    spread_x = (high / low) if (low and high and low > 0) else None
    families = tuple(m.value for m in tam.method_families_used) if tam is not None else ()
    independence = tam.independence_score if tam is not None else 0.0
    limitations = _limitations(tam)
    # The "inputs are modeled" caveat must reflect MODELED INPUTS specifically —
    # not any limitation. A scope warning is a limitation but not a modeled input,
    # so gate the caveat on the TAM's own modeled/synthetic flags (review #128).
    has_modeled = tam is not None and (tam.uses_modeled_composites or tam.uses_synthetic_primitives)

    sections: list[ReportSection] = []
    # Executive summary leads (answer-first pyramid).
    sections.append(
        ReportSection(
            key="executive_summary",
            title="Executive summary",
            summary=executive_summary(
                concept_name=base.concept_name,
                low=low,
                mid=mid,
                high=high,
                n_method_families=len(families),
                independence_score=independence,
                has_modeled=has_modeled,
            ),
            chart="kpi_strip",
        )
    )
    # Market definition & scope leads the evidence — a premium report names what
    # is in/out of market before sizing it (the #1 thing a drifting definition breaks).
    sections.append(
        ReportSection(
            key="market_definition_scope",
            title="Market definition & scope",
            summary=_scope_summary(tam),
            is_gap=tam is None or getattr(tam, "scope", None) is None,
        )
    )
    for key, title, cats in _SECTION_CATEGORIES:
        answers = tuple(a for cat in cats for a in by_category.get(cat, []))
        answered = tuple(a for a in answers if a.status == "answered")
        if key == "triangulation":
            summary = triangulation_note(
                n_method_families=len(families), low=low, high=high, spread_x=spread_x
            )
        elif answered:
            summary = " ".join(a.narrative for a in answered[:3])
        else:
            summary = (
                f"No sourced data in the bank answers {title.lower()} for this market yet — "
                f"an honest gap, surfaced rather than fabricated."
            )
        sections.append(
            ReportSection(
                key=key,
                title=title,
                summary=summary,
                chart=_SECTION_CHART.get(key),
                answers=answers,
                is_gap=not answered,
            )
        )

    if mid is not None:
        headline = f"{base.concept_name}: a {usd(mid)} market"
        subtitle = (
            f"{len(families)} method famil{'ies' if len(families) != 1 else 'y'}"
            f" · independence {independence:.2f}"
            + (f" · {usd(low)} to {usd(high)}" if low is not None and high is not None else "")
        )
    else:
        headline = f"{base.concept_name}: unsizable from the curated bank"
        subtitle = "Every numeric question is an honest gap — no fabricated figure."

    return PremiumReport(
        concept_slug=base.concept_slug,
        concept_name=base.concept_name,
        state_hash=tam.state_hash if tam is not None else None,
        headline=headline,
        subtitle=subtitle,
        range_low=low,
        range_mid=mid,
        range_high=high,
        spread_x=spread_x,
        independence_score=independence,
        method_families=families,
        sections=tuple(sections),
        sources=_dedup_sources(base.answers),
        limitations=limitations,
    )


def assemble_premium_report_for_tam(registry: Registry, tam: TAMOutput) -> PremiumReport:
    """Premium report bound to a specific TAM (reuses the GAP-1 fix)."""
    base = assemble_report_for_tam(registry, tam)
    return build_premium_report(tam, base)
