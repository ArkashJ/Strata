"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

the_default_data_dir = "data"


class Settings(BaseSettings):
    """Strata runtime configuration.

    All fields are environment-driven with the ``STRATA_`` prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="STRATA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: str = Field(default=the_default_data_dir)
    database_url: str | None = Field(default=None)

    # LLM backend
    llm_backend: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    exa_api_key: str | None = Field(default=None)

    # Connector API keys
    bls_api_key: str | None = Field(default=None)
    fred_api_key: str | None = Field(default=None)
    census_api_key: str | None = Field(default=None)
    eia_api_key: str | None = Field(default=None)
    nass_api_key: str | None = Field(default=None)
    dune_api_key: str | None = Field(default=None)
    alpha_vantage_api_key: str | None = Field(default=None)
    nasdaq_data_link_api_key: str | None = Field(default=None)

    # Additional connector / data-source API keys
    sec_api_key: str | None = Field(default=None)
    sec_user_agent: str | None = Field(default=None)
    polymarket_api_key: str | None = Field(default=None)
    metaculus_api_token: str | None = Field(default=None)
    manifold_api_key: str | None = Field(default=None)
    crunchbase_api_key: str | None = Field(default=None)
    opencorporates_api_key: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)
    serper_api_key: str | None = Field(default=None)
    brave_search_api_key: str | None = Field(default=None)
    perplexity_api_key: str | None = Field(default=None)
    producthunt_client_id: str | None = Field(default=None)
    producthunt_client_secret: str | None = Field(default=None)
    producthunt_dev_token: str | None = Field(default=None)
    coingecko_api_key: str | None = Field(default=None)
    etherscan_api_key: str | None = Field(default=None)
    reddit_user_agent: str | None = Field(default=None)

    # API auth + rate limit
    api_keys: str | None = Field(default=None)
    rate_limit_per_minute: int = Field(default=120)
    cors_origin: str | None = Field(default=None)
    cors_origin_regex: str | None = Field(default=None)
    seed_on_boot: bool = Field(default=False)
    offline: bool = Field(default=False)

    # Integrations (OAuth connectors)
    integrations_secret_key: str | None = Field(default=None)
    hubspot_client_id: str | None = Field(default=None)
    hubspot_client_secret: str | None = Field(default=None)
    hubspot_redirect_uri: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
