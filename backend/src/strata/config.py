"""Runtime configuration loaded from environment via pydantic-settings.

Single source of truth for env-driven settings. Import `settings` anywhere
that needs config; never read `os.environ` directly outside this module.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

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

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ── Wave 3 substrate: auth / rate-limit / metering ──────────────────
    # Comma-separated ``rawkey:org_id`` pairs seeding the in-process key store
    # (dev/self-host). Prod also reads hashed keys from the ``api_keys`` table.
    api_keys_raw: str = ""
    # When True, protected (write/compute/LLM) routes require a valid API key.
    # Off in dev/test by default so the curated read API stays open locally.
    require_auth: bool = False
    # Token-bucket rate limit per key on LLM/compute routes.
    rate_limit_rpm: int = Field(default=60, ge=1)

    # ── Clerk session-JWT bridge (PR 1 / KTD-3) ────────────────────────
    # When ``clerk_jwks_url`` is None (default), the Clerk verifier is INERT —
    # it returns None with no network call, so anonymous permalinks resolve with
    # no 401 storm. Set it to the Clerk instance's JWKS endpoint to enable Bearer
    # auth. ``clerk_issuer`` / ``clerk_audience`` are verified only when set.
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    clerk_audience: str | None = None

    # ── OAuth 2.1 Authorization Server (hosted-MCP web connectors) ──────
    # Co-hosts an AS so claude.ai / ChatGPT "Add custom connector" UIs (which
    # have no static-header field — OAuth only) can connect in one click. Both
    # must be set for the AS to come alive; when either is None the metadata /
    # /oauth routes return 404 (honest "not configured"), mirroring
    # ``portfolio_enabled``. ``oauth_issuer`` is the API base (scheme+host, no
    # trailing path) and MUST equal the metadata-serving origin byte-for-byte —
    # the #1 cause of claude.ai connect failures. ``mcp_resource_url`` is the
    # ``…/mcp/`` URL byte-exact as users type it (trailing slash load-bearing);
    # it is the RFC 8707 audience an issued token is bound to.
    oauth_issuer: str | None = None
    mcp_resource_url: str | None = None
    oauth_access_ttl_seconds: int = Field(default=3600, ge=1)
    oauth_refresh_ttl_seconds: int = Field(default=2592000, ge=1)
    # Authorization codes are single-use and exchanged within seconds of consent;
    # a short life bounds the replay window. Threaded like the token TTLs (not a
    # magic literal in the route) so it is tunable per deploy.
    oauth_code_ttl_seconds: int = Field(default=600, ge=1)
    # Absolute URL of the frontend's Clerk-gated consent page (e.g.
    # ``https://stratabank.vercel.app/oauth/authorize``). ``GET /oauth/authorize``
    # (which arrives cross-origin with no Clerk cookie) 302s the browser here so
    # the user signs in + consents; the page then POSTs the decision back with a
    # Clerk session token. When unset, the AS cannot complete an interactive
    # authorization and ``GET /oauth/authorize`` returns 503 ("consent UI not
    # configured") rather than minting without a real identity.
    oauth_consent_url: str | None = None

    @property
    def oauth_enabled(self) -> bool:
        """The AS is live only when both the issuer and the resource URL are set."""
        return bool(self.oauth_issuer and self.mcp_resource_url)

    # Regex for additional allowed origins — used for Vercel preview deploys whose
    # subdomain carries a per-deploy hash (so an exact-origin list can't enumerate
    # them). e.g. ``https://strata-[a-z0-9-]+-arkashjs-projects\.vercel\.app``.
    cors_origin_regex: str | None = None

    data_dir: str = "data"

    # ── Portfolio sizing surface (P1) — ships dark (F6) ──────────────────
    # When off (default), the migration still creates the ``companies`` table,
    # but the CLI / MCP / HTTP WRITE surfaces refuse with a "disabled" error.
    # GET /portfolio still serves the cached demo subset so the page renders
    # (read path stays F3-safe — no live LLM/Exa ever). Local dev sets =1.
    portfolio_enabled: bool = False

    # ── SQLAlchemy async engine pool (prod-tuned defaults) ──────────────
    # Wired into create_async_engine via ``engine_pool_kwargs()``. Defaults
    # are sized for a single Railway service container fronting a managed
    # Postgres; raise pool_size/max_overflow with more workers. pool_recycle
    # below the provider's idle-connection cutoff avoids stale-socket errors.
    db_pool_size: int = Field(default=10, ge=1, description="Persistent connections per process.")
    db_max_overflow: int = Field(default=5, ge=0, description="Burst connections beyond pool_size.")
    db_pool_timeout: int = Field(
        default=30, gt=0, description="Seconds to wait for a connection before erroring."
    )
    db_pool_recycle: int = Field(
        default=1800, gt=0, description="Recycle connections older than N seconds."
    )
    db_pool_pre_ping: bool = Field(
        default=True, description="Validate connections before checkout (drops dead sockets)."
    )

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
    dune_api_key: str | None = None  # Dune Analytics on-chain query API (X-Dune-API-Key)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    github_token: str | None = None
    stack_exchange_key: str | None = None
    twitter_bearer_token: str | None = None

    # ── Additional connector / data-source API keys ─────────────────────
    # New providers wired by the v0.3+ connector expansion. Each is read from
    # ``STRATA_<NAME>`` and defaults to None so the keyless/fallback path holds.
    sec_api_key: str | None = None
    sec_user_agent: str | None = None
    polymarket_api_key: str | None = None
    metaculus_api_token: str | None = None
    manifold_api_key: str | None = None
    crunchbase_api_key: str | None = None
    opencorporates_api_key: str | None = None
    tavily_api_key: str | None = None
    serper_api_key: str | None = None
    brave_search_api_key: str | None = None
    perplexity_api_key: str | None = None
    producthunt_client_id: str | None = None
    producthunt_client_secret: str | None = None
    producthunt_dev_token: str | None = None
    coingecko_api_key: str | None = None
    etherscan_api_key: str | None = None
    reddit_user_agent: str | None = None

    # v0.3 CLI behaviour.
    # ``strata goal`` reads this directly from os.environ for clarity; it is
    # listed here so pydantic-settings does not warn about unknown env vars.
    offline: bool = False

    def engine_pool_kwargs(self) -> dict[str, Any]:
        """Keyword args for ``sqlalchemy.create_async_engine`` pool tuning."""
        return {
            "pool_size": self.db_pool_size,
            "max_overflow": self.db_max_overflow,
            "pool_timeout": self.db_pool_timeout,
            "pool_recycle": self.db_pool_recycle,
            "pool_pre_ping": self.db_pool_pre_ping,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
