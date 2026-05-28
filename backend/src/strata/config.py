"""Runtime configuration loaded from environment via pydantic-settings.

Single source of truth for env-driven settings. Import `settings` anywhere
that needs config; never read `os.environ` directly outside this module.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "test", "prod"]


def _find_env_file() -> str:
    """Search CWD and parent directories for .env."""
    for candidate in [Path(".env"), Path("../.env"), Path("../../.env")]:
        if candidate.exists():
            return str(candidate.resolve())
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        env_prefix="STRATA_",
        extra="ignore",
    )

    env: Env = "dev"
    log_level: str = "INFO"
    log_json: bool = False

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://strata:strata@localhost:5432/strata"),
        description="Async DSN. Must use the asyncpg driver.",
    )

    # SQLAlchemy connection-pool sizing. Defaults are tuned for a small
    # single-instance deploy (Railway). Bump pool_size/max_overflow if you run
    # more concurrent workers; lower pool_recycle if the DB drops idle conns.
    db_pool_size: int = Field(
        default=5, description="Persistent connections kept open in the pool."
    )
    db_max_overflow: int = Field(
        default=10, description="Extra connections allowed above pool_size under load."
    )
    db_pool_timeout: float = Field(
        default=30.0, description="Seconds to wait for a free connection before erroring."
    )
    db_pool_recycle: int = Field(
        default=1800, description="Recycle connections older than this many seconds."
    )
    db_pool_pre_ping: bool = Field(
        default=True, description="Test a connection with a ping before handing it out."
    )

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    data_dir: str = "data"

    bls_api_key: str | None = None
    fred_api_key: str | None = None
    census_api_key: str | None = None
    kalshi_api_key: str | None = None
    kalshi_private_key_path: str | None = None

    eia_api_key: str | None = None
    usda_nass_api_key: str | None = None
    openfda_api_key: str | None = None
    comtrade_api_key: str | None = None

    # v0.3 connectors (PR-A).
    alpha_vantage_api_key: str | None = None
    nasdaq_data_link_api_key: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    github_token: str | None = None
    stack_exchange_key: str | None = None
    twitter_bearer_token: str | None = None

    # v0.3 CLI behaviour.
    # ``strata goal`` reads this directly from os.environ for clarity; it is
    # listed here so pydantic-settings does not warn about unknown env vars.
    offline: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
