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
from strata.models import ConceptQuestionReport, QuestionCategory
from strata.registry import Registry, RegistryError
from strata.report import assemble_report

router = APIRouter(prefix="/report", tags=["report"])

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
