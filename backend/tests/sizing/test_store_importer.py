"""Company store + CSV importer tests (spec §4, §7)."""

from __future__ import annotations

from pathlib import Path

from strata.models import CompanyRecord, normalize_domain
from strata.sizing.importer import parse_portfolio_csv
from strata.sizing.store import CompanyStore


def test_normalize_domain() -> None:
    assert normalize_domain("HTTPS://Cursor.com/pricing") == "cursor.com"
    assert normalize_domain("www.Acme.io") == "acme.io"
    assert normalize_domain("  Foo.AI  ") == "foo.ai"


def test_store_roundtrip_and_idempotency(tmp_path: Path) -> None:
    store = CompanyStore(tmp_path / "p.json")
    rows = [
        CompanyRecord(name="Cursor", domain="cursor.com", vertical="Dev"),
        CompanyRecord(name="Acme", domain="acme.io", vertical="Fintech"),
    ]
    added, skipped = store.upsert_many(rows)
    assert (added, skipped) == (2, 0)

    # Re-import the same rows → idempotent, no duplicates.
    added2, skipped2 = store.upsert_many(rows)
    assert (added2, skipped2) == (0, 2)

    # Survives a reload from disk.
    reloaded = CompanyStore(tmp_path / "p.json")
    assert reloaded.counts()["total"] == 2
    assert reloaded.get("cursor.com") is not None


def test_store_list_filters(tmp_path: Path) -> None:
    store = CompanyStore(tmp_path / "p.json")
    store.upsert_many(
        [
            CompanyRecord(name="A", domain="a.com", vertical="Dev", status="sized"),
            CompanyRecord(name="B", domain="b.com", vertical="Dev", status="unsized"),
            CompanyRecord(name="C", domain="c.com", vertical="Health", status="unsizable"),
        ]
    )
    assert len(store.list(status="sized")) == 1
    assert len(store.list(vertical="Dev")) == 2
    assert store.counts() == {"total": 3, "sized": 1, "unsized": 1, "unsizable": 1}


def test_parse_real_csv(tmp_path: Path) -> None:
    csv = tmp_path / "Cos.csv"
    csv.write_text(
        "﻿Name,Website,Industry Vertical\n"
        "Cursor,cursor.com,Dev\n"
        "11x,11x.ai,Agents\n"
        "Blankvert,blank.co,\n"
        "“,voilo.co.uk,Finance & Accounting\n",  # junk lone-quote name → skipped
        encoding="utf-8",
    )
    rows = parse_portfolio_csv(csv)
    names = {r.name for r in rows}
    assert "Cursor" in names
    assert "11x" in names
    # Blank vertical becomes None.
    blank = next(r for r in rows if r.name == "Blankvert")
    assert blank.vertical is None
    # The lone-quote junk row is dropped.
    assert "“" not in names
