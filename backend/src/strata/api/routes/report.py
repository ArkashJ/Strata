"""Question-driven market-report routes (PR4).

``GET /report`` lists the curated analysis-question catalog; ``GET
/report/{concept_slug}`` assembles the full report for one concept — purely
from the registry and the in-process evaluator, never an LLM. Every figure in
the response carries provenance or a reproducible TAM-field synthesis (Q20).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from strata.api.deps import get_registry
from strata.api.responses import error
from strata.db.tams import get_tam_from_db_safe
from strata.models import ConceptQuestionReport, QuestionCategory
from strata.registry import Registry, RegistryError
from strata.report import assemble_report, assemble_report_for_tam

router = APIRouter(prefix="/report", tags=["report"])

# A second router without the /report prefix for the TAM-bound report (it hangs
# off the /tam/<hash> permalink, not the /report catalog).
tam_report_router = APIRouter(tags=["report"])

_REG = Depends(get_registry)


class QuestionSummary(BaseModel):
    question_id: str
    prompt: str
    category: QuestionCategory
    lenses: tuple[str, ...]


@router.get(
    "",
    response_model=list[QuestionSummary],
    summary="List analysis questions",
    description="Return the curated analysis-question catalog with each question's category and lenses.",
)
async def list_questions(
    reg: Registry = _REG,
) -> list[QuestionSummary]:
    return [
        QuestionSummary(
            question_id=q.question_id,
            prompt=q.prompt,
            category=q.category,
            lenses=tuple(lens.value for lens in q.lenses),
        )
        for q in reg.questions.values()
    ]


@router.get(
    "/{concept_slug}",
    response_model=ConceptQuestionReport,
    summary="Assemble a concept's market report",
    description=(
        "Resolve every applicable analysis question for one concept against the "
        "registry and the in-process evaluator. Each numeric answer is sourced or "
        "TAM-derived; unsizable inputs degrade to honest gaps, never fabrications."
    ),
    responses=error(404, "Concept not found."),
)
async def get_report(
    concept_slug: str,
    reg: Registry = _REG,
) -> ConceptQuestionReport:
    try:
        return assemble_report(reg, concept_slug)
    except RegistryError as exc:
        raise HTTPException(404, f"concept {concept_slug!r} not found") from exc


@tam_report_router.get(
    "/tam/{state_hash}/report",
    response_model=ConceptQuestionReport,
    summary="Assemble the report BOUND to a specific TAM",
    description=(
        "Assemble the market report for the exact TAM identified by ``state_hash`` "
        "— its scenarios, convergence, independence, and scope — with no "
        "re-evaluation. A what-if build's report reflects the steered numbers, not "
        "a fresh size of the live concept (GAP-1)."
    ),
    responses=error(404, "TAM not found."),
)
async def get_report_for_tam(
    state_hash: str,
    reg: Registry = _REG,
) -> ConceptQuestionReport:
    tam = reg.tam_outputs.get(state_hash)
    if tam is None:
        # The in-memory cache is FIFO-capped + reset on restart; fall back to the
        # durable store so a shared permalink keeps resolving (mirrors GET /tam).
        tam = await get_tam_from_db_safe(state_hash)
        if tam is not None:
            reg.remember_tam(tam)
    if tam is None:
        raise HTTPException(404, f"tam {state_hash!r} not found")
    try:
        return assemble_report_for_tam(reg, tam)
    except RegistryError as exc:
        raise HTTPException(404, f"concept for tam {state_hash!r} not found") from exc
