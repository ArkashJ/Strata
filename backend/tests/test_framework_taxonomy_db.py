"""The framework taxonomy must survive the Postgres round-trip (prod path).

Without persisted columns, ``Registry.from_db()`` reconstructs every framework
as a canonical (no parent, no modifiers) — the validator then fires on the wrong
data and the whole gate is inert in prod. This test seeds YAML → DB and reloads
via ``from_db`` to prove the taxonomy lands in Postgres and reads back intact.

Requires a live Postgres migrated to head (CI provides one; skipped locally when
unreachable or when migration 011 hasn't run).
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from strata.config import settings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


pytestmark = pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")


async def _columns_present() -> bool:
    import asyncpg

    conn = await asyncpg.connect(str(settings.database_url).replace("+asyncpg", ""))
    try:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'frameworks'"
        )
        names = {r["column_name"] for r in cols}
        return {"parent_lens_shape", "realism_modifiers"} <= names
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_taxonomy_survives_db_round_trip() -> None:
    from strata.db.sync import sync_yaml_to_db
    from strata.registry import Registry
    from strata.validator.cross_record import cross_record_check

    if not await _columns_present():
        pytest.skip("frameworks taxonomy columns not migrated (run alembic upgrade head)")

    await sync_yaml_to_db(DATA_DIR)
    reg = await Registry.from_db()

    canonical = [f for f in reg.frameworks.values() if f.parent_lens_shape is None]
    subs = [f for f in reg.frameworks.values() if f.parent_lens_shape is not None]
    # The taxonomy must read back from Postgres, not collapse to all-canonical.
    assert len(canonical) == 6, f"expected 6 canonical from DB, got {len(canonical)}"
    assert len(subs) >= 1 and all(s.realism_modifiers for s in subs), (
        "subframeworks lost their parent/modifiers on the DB round-trip"
    )
    taxonomy_issues = [i for i in cross_record_check(reg) if i.code == "cross.framework_taxonomy"]
    assert taxonomy_issues == [], "DB-backed registry fails the taxonomy gate"
