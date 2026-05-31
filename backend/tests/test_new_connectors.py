"""Smoke + cache + converter tests for the 7 new connectors (spec §4).

All tests are mock/fixture-based — no live API calls. Live smokes go through
``strata test-connectors`` and are gated on env-var presence.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from strata.connectors import (
    AlphaVantageClient,
    AlphaVantageClientError,
    AlphaVantageCompanyOverview,
    GitHubClient,
    GitHubRepo,
    NasdaqDataLinkClient,
    NasdaqDatasetMeta,
    NasdaqObservation,
    NasdaqTier,
    RedditClient,
    RedditClientError,
    StackExchangeClient,
    SubredditStats,
    TagInfo,
    TwitterClient,
    TwitterClientError,
    TwitterTweet,
    TwitterUser,
    YahooQuote,
    YFinanceClient,
    market_cap_to_primitive_yaml,
    nasdaq_observation_to_primitive_yaml,
    overview_to_source_yaml,
    quote_to_primitive_yaml,
    quote_to_source_yaml,
    repo_to_primitive_yaml,
    repo_to_source_yaml,
    subreddit_to_primitive_yaml,
    subreddit_to_source_yaml,
    tag_to_primitive_yaml,
    tag_to_source_yaml,
    user_to_primitive_yaml,
    user_to_source_yaml,
)

# ---------------------------------------------------------------------------
# Client construction / auth-gate
# ---------------------------------------------------------------------------


def test_alpha_vantage_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hermetic: the client falls back to settings.alpha_vantage_api_key when no
    # key is passed, so neutralize any developer .env value before asserting the
    # genuine keyless behavior.
    from strata.config import settings

    monkeypatch.setattr(settings, "alpha_vantage_api_key", None)
    monkeypatch.delenv("STRATA_ALPHA_VANTAGE_API_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    with pytest.raises(AlphaVantageClientError):
        AlphaVantageClient(api_key="")


def test_reddit_requires_both_credentials() -> None:
    with pytest.raises(RedditClientError):
        RedditClient(client_id="", client_secret="abc")
    with pytest.raises(RedditClientError):
        RedditClient(client_id="abc", client_secret="")


def test_twitter_requires_bearer_token() -> None:
    with pytest.raises(TwitterClientError):
        TwitterClient(bearer_token="")


def test_github_works_without_token(tmp_path: Path) -> None:
    # Unauthenticated GitHub access is allowed (60 req/h)
    client = GitHubClient(token=None, cache_dir=tmp_path)
    assert client.token is None
    client.close()


def test_nasdaq_works_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Nasdaq free datasets do not require a key. Hermetic: clear any developer
    # .env value so the keyless path is exercised deterministically.
    from strata.config import settings

    monkeypatch.setattr(settings, "nasdaq_data_link_api_key", None)
    monkeypatch.delenv("STRATA_NASDAQ_DATA_LINK_API_KEY", raising=False)
    monkeypatch.delenv("NASDAQ_DATA_LINK_API_KEY", raising=False)
    client = NasdaqDataLinkClient(api_key=None, cache_dir=tmp_path, tier=NasdaqTier.FREE)
    assert client.api_key is None
    client.close()


def test_stack_exchange_works_without_key(tmp_path: Path) -> None:
    client = StackExchangeClient(key=None, cache_dir=tmp_path)
    assert client.key is None
    client.close()


def test_yfinance_works_without_key(tmp_path: Path) -> None:
    client = YFinanceClient(cache_dir=tmp_path)
    client.close()


# ---------------------------------------------------------------------------
# Disk-cache mechanics (one representative test per client; all share the same
# _DiskCache implementation pattern)
# ---------------------------------------------------------------------------


def test_disk_cache_writes_and_reads(tmp_path: Path) -> None:
    client = AlphaVantageClient(api_key="X", cache_dir=tmp_path)
    payload: dict[str, object] = {"Symbol": "AAPL", "Name": "Apple"}
    client.cache.put('{"function": "OVERVIEW", "symbol": "AAPL"}', payload)
    cached = client.cache.get('{"function": "OVERVIEW", "symbol": "AAPL"}')
    assert cached is not None
    data, _mtime = cached
    assert data == payload
    client.close()


def test_disk_cache_clear(tmp_path: Path) -> None:
    client = AlphaVantageClient(api_key="X", cache_dir=tmp_path)
    client.cache.put("k1", {"v": 1})
    client.cache.put("k2", {"v": 2})
    assert client.clear_cache() == 2
    client.close()


# ---------------------------------------------------------------------------
# YAML converter shape (all converters must emit AtomicPrimitive-shaped dicts
# with snapshot_sha256 pinning per Q5)
# ---------------------------------------------------------------------------


def _accessed() -> date:
    return date(2026, 5, 27)


def _assert_atomic_primitive_shape(prim: dict[str, object]) -> None:
    assert prim["kind"] == "atomic_primitive"
    assert "slug" in prim
    assert prim["schema_version"] == 1
    assert "concept_slug" in prim
    assert "name" in prim
    assert "value" in prim and isinstance(prim["value"], int | float)
    unit = prim["unit"]
    assert isinstance(unit, dict) and "kind" in unit and "dimension" in unit
    assert "geo" in prim and "geo_perspective" in prim
    src = prim["source"]
    assert isinstance(src, dict)
    assert src["snapshot_sha256"] and isinstance(src["snapshot_sha256"], str)
    assert src["accessed"] == _accessed().isoformat()


def test_alpha_vantage_converters() -> None:
    overview = AlphaVantageCompanyOverview(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        market_cap_usd=3_500_000_000_000.0,
        ebitda=None,
        pe_ratio=28.5,
        dividend_yield=0.005,
        revenue_ttm=None,
        currency="USD",
    )
    prim = market_cap_to_primitive_yaml(
        overview, slug="av-aapl-mcap-2026", concept_slug="apple", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    unit = prim["unit"]
    assert isinstance(unit, dict)
    assert unit["dimension"] == "currency"
    assert unit["currency"] == "USD"
    src = overview_to_source_yaml(overview, accessed=_accessed())
    assert src["tier"] == "aggregator"


def test_nasdaq_converter() -> None:
    obs = NasdaqObservation(
        dataset_code="ORB",
        series_date=date(2024, 1, 1),
        values=(82.5,),
    )
    meta = NasdaqDatasetMeta(
        database_code="OPEC",
        dataset_code="ORB",
        name="OPEC Crude Oil Price",
        description="OPEC reference basket spot price",
        frequency="daily",
        newest_available_date="2024-01-02",
        oldest_available_date="2003-01-02",
        refreshed_at="2024-01-02T00:00:00Z",
        column_names=("Date", "Value"),
    )
    prim = nasdaq_observation_to_primitive_yaml(
        obs,
        slug="nasdaq-opec-orb-2024",
        concept_slug="oil-prices",
        meta=meta,
        accessed=_accessed(),
    )
    _assert_atomic_primitive_shape(prim)


def test_yfinance_converter() -> None:
    quote = YahooQuote(
        symbol="AAPL",
        price=185.50,
        currency="USD",
        market_cap=3_000_000_000_000.0,
        shares_outstanding=15_500_000_000,
        short_name="Apple Inc.",
        exchange="NasdaqGS",
        quote_as_of=datetime(2026, 5, 27, tzinfo=UTC),
    )
    prim = quote_to_primitive_yaml(
        quote, slug="yfin-aapl-2026", concept_slug="apple", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    src = quote_to_source_yaml(quote, accessed=_accessed())
    assert src["tier"] == "analyst"


def test_reddit_converter() -> None:
    stats = SubredditStats(
        name="MachineLearning",
        subscribers=2_900_000,
        active_user_count=4500,
        created_utc=datetime(2008, 6, 22, tzinfo=UTC),
        public_description="Machine learning community.",
        over_18=False,
    )
    prim = subreddit_to_primitive_yaml(
        stats, slug="reddit-ml-2026", concept_slug="ml-community", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    src = subreddit_to_source_yaml(stats, accessed=_accessed())
    assert src["tier"] == "community"


def test_github_converter() -> None:
    repo = GitHubRepo(
        full_name="vercel/next.js",
        stargazers_count=120_000,
        forks_count=26_000,
        open_issues_count=2300,
        subscribers_count=1500,
        language="JavaScript",
        created_at=datetime(2016, 10, 5, tzinfo=UTC),
        pushed_at=datetime(2026, 5, 26, tzinfo=UTC),
    )
    prim = repo_to_primitive_yaml(
        repo, slug="gh-vercel-nextjs-2026", concept_slug="js-frameworks", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    src = repo_to_source_yaml(repo, accessed=_accessed())
    assert src["tier"] == "community"


def test_stack_exchange_converter() -> None:
    tag = TagInfo(
        name="rust",
        site="stackoverflow",
        question_count=42_000,
        is_required=False,
        is_moderator_only=False,
    )
    prim = tag_to_primitive_yaml(
        tag, slug="so-rust-2026", concept_slug="rust-adoption", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    src = tag_to_source_yaml(tag, accessed=_accessed())
    assert src["tier"] == "community"


def test_twitter_user_converter() -> None:
    user = TwitterUser(
        id="2244994945",
        username="OpenAI",
        name="OpenAI",
        followers_count=2_500_000,
        following_count=10,
        tweet_count=1500,
        verified=True,
        created_at="2009-08-10T00:00:00Z",
    )
    prim = user_to_primitive_yaml(
        user, slug="x-openai-2026", concept_slug="openai-attention", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    src = user_to_source_yaml(user, accessed=_accessed())
    assert src["tier"] == "analyst"


def test_twitter_tweet_dataclass_is_frozen() -> None:
    """TwitterTweet is the second-endpoint return type; sanity check immutability."""
    t = TwitterTweet(
        id="1",
        author_id="2244994945",
        text="hello",
        created_at=None,
        retweet_count=0,
        like_count=0,
    )
    with pytest.raises((AttributeError, TypeError, Exception)):
        t.id = "2"  # type: ignore[misc]  # frozen dataclass


# ---------------------------------------------------------------------------
# Snapshot hash determinism — different payloads produce different hashes
# ---------------------------------------------------------------------------


def test_snapshot_hash_differs_for_different_values() -> None:
    """Different primitive values produce different source snapshot hashes (Q5)."""
    overview_a = AlphaVantageCompanyOverview(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector=None,
        industry=None,
        market_cap_usd=1_000.0,
        ebitda=None,
        pe_ratio=None,
        dividend_yield=None,
        revenue_ttm=None,
        currency="USD",
    )
    overview_b = AlphaVantageCompanyOverview(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector=None,
        industry=None,
        market_cap_usd=2_000.0,
        ebitda=None,
        pe_ratio=None,
        dividend_yield=None,
        revenue_ttm=None,
        currency="USD",
    )
    src_a = overview_to_source_yaml(overview_a, accessed=_accessed())
    src_b = overview_to_source_yaml(overview_b, accessed=_accessed())
    assert src_a["snapshot_sha256"] != src_b["snapshot_sha256"]


# ---------------------------------------------------------------------------
# Capabilities round-trip — the manifest function returns serializable JSON
# ---------------------------------------------------------------------------


def test_capabilities_serialize_to_json() -> None:
    """The router serializes manifests to JSON in its system prompt — make
    sure every spec round-trips cleanly via pydantic model_dump."""
    from strata.connectors import all_capabilities

    payload = [spec.model_dump() for spec in all_capabilities()]
    blob = json.dumps(payload)
    assert len(blob) > 1000  # sanity — non-trivial manifest payload
