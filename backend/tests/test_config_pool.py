"""Production pool config lives in Settings and is env-overridable."""

from __future__ import annotations

import pytest

from strata.config import Settings


def test_pool_defaults_present() -> None:
    s = Settings()
    assert isinstance(s.db_pool_size, int) and s.db_pool_size > 0
    assert isinstance(s.db_max_overflow, int) and s.db_max_overflow >= 0
    assert isinstance(s.db_pool_timeout, int) and s.db_pool_timeout > 0
    assert isinstance(s.db_pool_recycle, int) and s.db_pool_recycle > 0
    assert isinstance(s.db_pool_pre_ping, bool)


def test_pool_kwargs_shape() -> None:
    s = Settings()
    kwargs = s.engine_pool_kwargs()
    assert kwargs["pool_size"] == s.db_pool_size
    assert kwargs["max_overflow"] == s.db_max_overflow
    assert kwargs["pool_timeout"] == s.db_pool_timeout
    assert kwargs["pool_recycle"] == s.db_pool_recycle
    assert kwargs["pool_pre_ping"] == s.db_pool_pre_ping


def test_pool_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_DB_POOL_SIZE", "25")
    monkeypatch.setenv("STRATA_DB_MAX_OVERFLOW", "7")
    s = Settings()
    assert s.db_pool_size == 25
    assert s.db_max_overflow == 7
