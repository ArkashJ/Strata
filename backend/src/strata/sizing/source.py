"""Source one required input — connector (regulator) or Exa+guard (analyst).

Pure given injected client functions, so it is fully testable without network.
Strict priority (spec §5 step 3):

  a. connector hint  → live API → regulator tier + real value + sha256(response)
  b. else Exa search → fetch top real page → VERBATIM GUARD (§6/F1)
                       → analyst tier (org-PRIVATE first, F2) + url + sha256(text)
  c. NEVER an LLM-computed number — an input that can't be sourced stays unfilled.

This module owns step (b)'s guard call; (a) defers to ``connectors/_dispatch``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from .guard import GuardVerdict, verbatim_guard


@dataclass(frozen=True, slots=True)
class SourcedInput:
    """One sourced primitive value, ready for ``writer.upsert_primitive``."""

    role: str
    value: float
    tier: str  # regulator | analyst
    url: str
    snapshot_sha256: str
    visibility: str  # public | private  (analyst is private until promoted, F2)
    guard: GuardVerdict | None = None


# An ExaFetcher returns (url, page_text) for a role query, or None on no hit.
ExaFetcher = Callable[[str], "tuple[str, str] | None"]


def source_via_exa(
    role: str,
    query: str,
    candidate_value: float,
    *,
    fetcher: ExaFetcher,
    role_keywords: list[str] | None = None,
    second_fetcher: ExaFetcher | None = None,
) -> SourcedInput | None:
    """Locate ``candidate_value`` on a real fetched page and gate it (§6/F1).

    Returns a private analyst ``SourcedInput`` when the guard accepts, else
    ``None`` (the input stays unsourced — we never persist an unverified number).
    Public promotion is a SEPARATE, gated step (F2): a single corroborated hit is
    still org-private here.
    """
    hit = fetcher(query)
    if hit is None:
        return None
    url, page_text = hit

    second_text: str | None = None
    if second_fetcher is not None:
        second_hit = second_fetcher(query)
        if second_hit is not None:
            second_text = second_hit[1]

    verdict = verbatim_guard(
        candidate_value,
        page_text,
        role_keywords=role_keywords or [role],
        second_source_text=second_text,
    )
    if not verdict.eligible_private:
        return None

    snapshot = hashlib.sha256(page_text.encode()).hexdigest()
    return SourcedInput(
        role=role,
        value=verdict.value if verdict.value is not None else candidate_value,
        tier="analyst",
        url=url,
        snapshot_sha256=snapshot,
        visibility="private",  # F2: analyst is private-first, always
        guard=verdict,
    )
