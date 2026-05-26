"""Runtime configuration loaded from environment via pydantic-settings.

Single source of truth for env-driven settings. Import `settings` anywhere
that needs config; never read `os.environ` directly outside this module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "test", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"]
    )

    data_dir: str = "data"

    bls_api_key: str | None = None
    fred_api_key: str | None = None
    census_api_key: str | None = None
    kalshi_api_key: str | None = None
    kalshi_private_key_path: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
