"""MCP Prompts — guided report workflows (Phase 6).

A prompt encodes the back-and-forth loop a VC analyst should follow so the
driving agent applies domain expertise instead of ad-hoc tool calls. Each
returns a single user-role message that scripts the multi-step flow (refine
scope -> pick method -> size -> triangulate -> sensitivity -> assemble), naming
the exact Strata tools to call.

These are static templates (no LLM); ``{arg}`` placeholders are filled from the
caller's arguments. They never assert numbers — only orchestration.
"""

from __future__ import annotations

import mcp.types as types
from mcp.server import Server

_SIZE = (
    "Size the market for: {market}.\n\n"
    "Follow this loop using the Strata MCP tools:\n"
    "1. resolve_market / search_concepts to find the curated concept.\n"
    "2. size_tam to get the sourced, hash-pinned scenario tree.\n"
    "3. Inspect the convergence + independence_score; if a single method, say so honestly.\n"
    "4. build_tam to run a what-if on any assumption that looks aggressive.\n"
    "5. get_report_for_tam(<state_hash>) to assemble the report bound to that exact TAM.\n"
    "Cite every number by its resource_uri; never invent a figure."
)

_VERIFY = (
    "Verify this market claim: {claim}.\n\n"
    "1. Call verify_market_claim with the claim (and asserted_value if the claim names one).\n"
    "2. Report the verdict (supported / partially_supported / unsupported / unverifiable) with "
    "the Strata sourced range, spread, method families, and provenance.\n"
    "3. If unverifiable, state the honest gap — do NOT synthesize a number."
)

_REPORT = (
    "Assemble a consulting-grade market report for: {market}.\n\n"
    "1. size_tam to anchor the number.\n"
    "2. get_report_for_tam(<state_hash>) for the full sourced sections (exec summary, "
    "market definition + scope, TAM/SAM/SOM, triangulation, segmentation, competitive "
    "landscape, growth drivers, sensitivity, sources appendix, limitations).\n"
    "3. Surface every figure with its source + tier + snapshot; mark gaps as 'no data', "
    "never fabricate. The forwardable PDF lives at /tam/<hash>/report."
)

_PORTFOLIO = (
    "Size the portfolio: {portfolio}.\n\n"
    "1. import_portfolio with the company rows (idempotent on domain).\n"
    "2. size_company for each linked company (registry-first, offline-safe).\n"
    "3. list_portfolio to review sized vs honestly-unsizable rows.\n"
    "4. For each sized company, get_report_for_tam to defend the market it maps to."
)

_PROMPTS: dict[str, dict[str, object]] = {
    "strata.size": {
        "description": "Guided loop to size a market into a sourced TAM.",
        "template": _SIZE,
        "arguments": [("market", "The market / concept to size.", True)],
    },
    "strata.verify": {
        "description": "Guided loop to verify an AI-generated market claim against sourced data.",
        "template": _VERIFY,
        "arguments": [("claim", "The market claim to verify.", True)],
    },
    "strata.report": {
        "description": "Guided loop to assemble a consulting-grade, fully-sourced report.",
        "template": _REPORT,
        "arguments": [("market", "The market / concept to report on.", True)],
    },
    "strata.portfolio": {
        "description": "Guided loop to size a portfolio of companies.",
        "template": _PORTFOLIO,
        "arguments": [("portfolio", "A description of the portfolio to size.", True)],
    },
}


def register_prompts(server: Server) -> None:
    """Wire the prompts capability onto ``server``."""

    @server.list_prompts()
    async def _list_prompts() -> list[types.Prompt]:  # pyright: ignore[reportUnusedFunction]
        out: list[types.Prompt] = []
        for name, spec in _PROMPTS.items():
            args = [
                types.PromptArgument(name=a, description=d, required=req)
                for (a, d, req) in spec["arguments"]  # type: ignore[union-attr]
            ]
            out.append(
                types.Prompt(name=name, description=str(spec["description"]), arguments=args)
            )
        return out

    @server.get_prompt()
    async def _get_prompt(  # pyright: ignore[reportUnusedFunction]
        name: str, arguments: dict[str, str] | None
    ) -> types.GetPromptResult:
        spec = _PROMPTS.get(name)
        if spec is None:
            raise ValueError(f"unknown prompt {name!r}")
        template = str(spec["template"])
        # Fill only the placeholders the template declares; a missing arg renders
        # as the literal token so the prompt is still usable.

        class _Fill(dict[str, str]):
            def __missing__(self, key: str) -> str:
                return "{" + key + "}"

        text = template.format_map(_Fill(arguments or {}))
        return types.GetPromptResult(
            description=str(spec["description"]),
            messages=[
                types.PromptMessage(role="user", content=types.TextContent(type="text", text=text))
            ],
        )


__all__ = ["register_prompts"]
