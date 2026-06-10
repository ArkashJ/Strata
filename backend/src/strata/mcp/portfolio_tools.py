"""Write-capable MCP tools — portfolio import / size / list (spec §7).

The first MUTATING tools on the Strata MCP surface. They are gated two ways:

* ``STRATA_PORTFOLIO_ENABLED`` (F6) — off → every tool returns a disabled error,
  so a hosted server can't accept untrusted portfolio writes before review.
* authenticated principal — the local stdio transport is local-trust and uses
  ``org_id="default"``; the hosted ``/mcp`` transport sits behind the Wave-3
  API-key middleware. (Per-principal org threading on the hosted path is the
  deferred piece, §10.)

Sizing here is registry-first and OFFLINE-safe (``SizeOptions()`` defaults) — an
MCP client can never trigger a live LLM/Exa call, so it can never receive an
unsourced number (the same Q20 guarantee the read tools give).
"""

from __future__ import annotations

from typing import Any

from ..config import settings
from ..models import CompanyRecord
from ..registry import Registry
from ..sizing.demo import load_demo_portfolio
from ..sizing.service import SizeOptions
from ..sizing.service import size_company as _size_company
from ..sizing.store import CompanyStore
from ..sizing.suggest import near_miss_slugs
from .context import current_org_id


def _disabled() -> dict[str, Any]:
    return {
        "error": "portfolio surface disabled",
        "detail": "Set STRATA_PORTFOLIO_ENABLED=1 to enable portfolio write tools (F6).",
    }


def _store() -> CompanyStore:
    # Hosted /mcp: the authenticated caller's org (threaded via the auth
    # middleware ContextVar). Local stdio: "default" (local-trust). So two
    # tenants writing through the hosted connector never share a portfolio.
    return CompanyStore(org_id=current_org_id())


def import_portfolio(reg: Registry, *, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """[WRITE] Link a list of companies to your org (idempotent on domain)."""
    if not settings.portfolio_enabled:
        return _disabled()
    org = current_org_id()
    records = [
        CompanyRecord(
            org_id=org,
            name=str(r.get("name", "")).strip(),
            domain=str(r.get("domain", "")).strip(),
            vertical=(str(r["vertical"]) if r.get("vertical") else None),
        )
        for r in rows
        if str(r.get("name", "")).strip()
    ]
    added, skipped = _store().upsert_many(records)
    return {"imported": added, "existing": skipped, "parsed": len(records), "org_id": org}


def add_portfolio_company(
    reg: Registry,
    *,
    name: str,
    domain: str = "",
    vertical: str | None = None,
    market_concept_slug: str | None = None,
    size: bool = False,
) -> dict[str, Any]:
    """[WRITE] Add ONE company to your org — the single-row twin of
    ``import_portfolio`` (agent parity with ``strata portfolio add``).

    An explicit ``market_concept_slug`` that isn't in the registry is an honest
    error with near-miss suggestions, never a fuzzy reroute (ADV-1 / Q20: a
    confidently wrong market is worse than a refusal)."""
    if not settings.portfolio_enabled:
        return _disabled()
    name = name.strip()
    if not name:
        return {"error": "name must be non-empty"}
    if market_concept_slug is not None and market_concept_slug not in reg.concepts:
        return {
            "error": "unknown_market_concept_slug",
            "detail": (
                f"market_concept_slug {market_concept_slug!r} is not in the registry; "
                "explicit slugs are never fuzzy-rerouted."
            ),
            "suggestions": near_miss_slugs(reg, market_concept_slug),
        }
    org = current_org_id()
    store = _store()
    rec = CompanyRecord(
        org_id=org,
        name=name,
        domain=domain.strip(),
        vertical=vertical,
        market_concept_slug=market_concept_slug,
    )
    added, _skipped = store.upsert_many([rec])
    if added:
        action = "added"
    else:
        # Re-add carrying NEW info updates the row (CLI ADV-3 parity); a
        # re-add with no new info stays idempotent.
        stored = store.get(rec.key) or rec
        changed = (
            market_concept_slug is not None and stored.market_concept_slug != market_concept_slug
        ) or (vertical is not None and stored.vertical != vertical)
        if changed:
            if market_concept_slug is not None:
                stored.market_concept_slug = market_concept_slug
            if vertical is not None:
                stored.vertical = vertical
            store.save(stored)
            action = "updated"
        else:
            action = "existing"
    out: dict[str, Any] = {"action": action, "key": rec.key, "org_id": org, "name": name}
    if not size:
        return out
    target = store.get(rec.key) or rec
    res = _size_company(reg, target, opts=SizeOptions())
    store.save(res.company)
    out.update(
        {
            "status": res.company.status,
            "market_concept_slug": res.company.market_concept_slug,
            "tam_value": res.company.tam_value,
            "reason": res.company.reason,
        }
    )
    if res.tam is not None:
        out["state_hash"] = res.tam.state_hash
    return out


def size_company(
    reg: Registry, *, domain: str | None = None, name: str | None = None
) -> dict[str, Any]:
    """[WRITE] Size one linked company registry-first (offline-safe). Returns the
    sourced TAM + provenance, or an honest ``unsizable`` reason."""
    if not settings.portfolio_enabled:
        return _disabled()
    key = (domain or name or "").strip()
    if not key:
        return {"error": "provide a domain or name"}
    store = _store()
    rec = store.get(key)
    if rec is None:
        # Allow ad-hoc sizing of a not-yet-imported company.
        rec = CompanyRecord(org_id=current_org_id(), name=name or key, domain=domain or "")
    res = _size_company(reg, rec, opts=SizeOptions())
    store.save(res.company)
    out: dict[str, Any] = {
        "name": rec.name,
        "domain": rec.domain,
        "status": res.company.status,
        "market_concept_slug": res.company.market_concept_slug,
        "tam_value": res.company.tam_value,
        "reason": res.company.reason,
    }
    if res.tam is not None:
        out["state_hash"] = res.tam.state_hash
        out["method_families"] = [m.value for m in res.tam.method_families_used]
    return out


def list_portfolio(
    reg: Registry,
    *,
    status: str | None = None,
    vertical: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """[READ] Portfolio rows + progress counts. Falls back to the cached demo
    subset when the local store is empty (so the demo works out of the box)."""
    store = _store()
    rows = store.list(status=status, vertical=vertical, limit=limit)  # type: ignore[arg-type]
    if not rows:
        demo = load_demo_portfolio()
        if status:
            demo = [r for r in demo if r.get("status") == status]
        if vertical:
            demo = [r for r in demo if str(r.get("vertical") or "").lower() == vertical.lower()]
        if limit:
            demo = demo[:limit]
        return {"source": "cached_demo", "counts": _demo_counts(), "companies": demo}
    return {
        "source": "store",
        "counts": store.counts(),
        "companies": [r.model_dump(mode="json") for r in rows],
    }


def _demo_counts() -> dict[str, int]:
    out = {"total": 0, "sized": 0, "unsized": 0, "unsizable": 0}
    for r in load_demo_portfolio():
        out["total"] += 1
        key = str(r.get("status", "unsized"))
        out[key] = out.get(key, 0) + 1
    return out
