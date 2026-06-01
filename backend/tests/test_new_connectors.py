"""Smoke + cache + converter tests for the 7 new connectors (spec §4).

All tests are mock/fixture-based — no live API calls. Live smokes go through
``strata test-connectors`` and are gated on env-var presence.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx as _httpx
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
from strata.connectors import github as _gh
from strata.connectors import reddit as _rd
from strata.connectors import stack_exchange as _se
from strata.connectors import twitter as _tw

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


# ===========================================================================
# Connector-expansion batch: reddit / github / stack_exchange / twitter
# (P0 converter-only emits + new parse methods, all mocked via MockTransport)
# ===========================================================================


def _mock_client(handler: object, ctor: object, **kwargs: object) -> object:
    """Build a client whose internal httpx.Client uses a MockTransport.

    We construct normally (cache_dir from tmp_path), then swap the transport so
    no real network is touched.
    """
    client = ctor(**kwargs)  # type: ignore[operator]
    client._client = _httpx.Client(  # type: ignore[attr-defined]
        transport=_httpx.MockTransport(handler),  # type: ignore[arg-type]
        headers=client._client.headers,  # type: ignore[attr-defined]
    )
    return client


def _sha_ok(prim: dict[str, object]) -> None:
    src = prim["source"]
    assert isinstance(src, dict)
    sha = src["snapshot_sha256"]
    assert isinstance(sha, str) and len(sha) == 64


# --- reddit ----------------------------------------------------------------


def _reddit_about(name: str, subs: int, active: int | None) -> dict[str, object]:
    return {
        "data": {
            "display_name": name,
            "subscribers": subs,
            "active_user_count": active,
            "created_utc": 1213900000,
            "public_description": "desc",
            "over18": False,
        }
    }


def test_reddit_active_users_converter_emits_pinned_primitive() -> None:
    stats = _rd.SubredditStats(
        name="MachineLearning",
        subscribers=2_900_000,
        active_user_count=4500,
        created_utc=datetime(2008, 6, 22, tzinfo=UTC),
        public_description="ml",
        over_18=False,
    )
    prim = _rd.active_users_to_primitive_yaml(
        stats, slug="reddit-ml-active-2026", concept_slug="ml-community", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    _sha_ok(prim)
    assert prim["value"] == 4500.0
    with pytest.raises(_rd.RedditClientError):
        _rd.active_users_to_primitive_yaml(
            _rd.SubredditStats(
                name="x",
                subscribers=1,
                active_user_count=None,
                created_utc=datetime(2020, 1, 1, tzinfo=UTC),
                public_description="",
                over_18=False,
            ),
            slug="x",
            concept_slug="x",
            accessed=_accessed(),
        )


def test_reddit_get_subreddits_about_batch_returns_response(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        if request.url.path == "/api/v1/access_token":
            return _httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        name = request.url.path.split("/")[2]
        return _httpx.Response(200, json=_reddit_about(name, 100, 5))

    client = _mock_client(
        handler, _rd.RedditClient, client_id="id", client_secret="sec", cache_dir=tmp_path
    )
    resp = client.get_subreddits_about(["MachineLearning", "LocalLLaMA"])  # type: ignore[attr-defined]
    assert isinstance(resp, _rd.RedditResponse)
    assert len(resp.items) == 2
    assert {i.name for i in resp.items} == {"MachineLearning", "LocalLLaMA"}
    client.close()  # type: ignore[attr-defined]


def test_reddit_search_subreddits_parses_matches(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        if request.url.path == "/api/v1/access_token":
            return _httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return _httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "data": {
                                "display_name": "MachineLearning",
                                "subscribers": 99,
                                "over18": False,
                            }
                        },
                        {"data": {"subscribers": 1}},  # no name → skipped
                    ]
                }
            },
        )

    client = _mock_client(
        handler, _rd.RedditClient, client_id="id", client_secret="sec", cache_dir=tmp_path
    )
    matches = client.search_subreddits("machine learning")  # type: ignore[attr-defined]
    assert len(matches) == 1
    assert isinstance(matches[0], _rd.SubredditMatch)
    assert matches[0].name == "MachineLearning"
    client.close()  # type: ignore[attr-defined]


def test_reddit_token_failure_is_client_error(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(500, json={"error": "boom"})

    client = _mock_client(
        handler, _rd.RedditClient, client_id="id", client_secret="sec", cache_dir=tmp_path
    )
    with pytest.raises(_rd.RedditClientError):
        client.get_subreddit_about("x")  # type: ignore[attr-defined]
    client.close()  # type: ignore[attr-defined]


# --- github ----------------------------------------------------------------


def _repo() -> _gh.GitHubRepo:
    return _gh.GitHubRepo(
        full_name="vercel/next.js",
        stargazers_count=120_000,
        forks_count=26_000,
        open_issues_count=2300,
        subscribers_count=1500,
        language="JavaScript",
        created_at=datetime(2016, 10, 5, tzinfo=UTC),
        pushed_at=datetime(2026, 5, 26, tzinfo=UTC),
    )


def test_github_p0_converters_emit_pinned_primitives() -> None:
    repo = _repo()
    forks = _gh.forks_to_primitive_yaml(
        repo, slug="gh-forks", concept_slug="js", accessed=_accessed()
    )
    watchers = _gh.watchers_to_primitive_yaml(
        repo, slug="gh-watch", concept_slug="js", accessed=_accessed()
    )
    issues = _gh.open_issues_to_primitive_yaml(
        repo, slug="gh-iss", concept_slug="js", accessed=_accessed()
    )
    for prim, val in ((forks, 26_000.0), (watchers, 1500.0), (issues, 2300.0)):
        _assert_atomic_primitive_shape(prim)
        _sha_ok(prim)
        assert prim["value"] == val
    # distinct snapshot slugs/hashes per metric
    srcs = [p["source"]["slug"] for p in (forks, watchers, issues)]  # type: ignore[index]
    assert len(set(srcs)) == 3


def test_github_watchers_converter_requires_subscribers() -> None:
    repo = _gh.GitHubRepo(
        full_name="a/b",
        stargazers_count=1,
        forks_count=0,
        open_issues_count=0,
        subscribers_count=None,
        language=None,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        pushed_at=None,
    )
    with pytest.raises(_gh.GitHubClientError):
        _gh.watchers_to_primitive_yaml(repo, slug="x", concept_slug="x", accessed=_accessed())


def test_github_contributors_count_reads_link_last_page(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        link = (
            '<https://api.github.com/repos/o/r/contributors?per_page=1&page=2>; rel="next", '
            '<https://api.github.com/repos/o/r/contributors?per_page=1&page=412>; rel="last"'
        )
        return _httpx.Response(200, json=[{"login": "a"}], headers={"Link": link})

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    cc = client.get_repo_contributors_count("o", "r")  # type: ignore[attr-defined]
    assert isinstance(cc, _gh.ContributorCount)
    assert cc.count == 412
    client.close()  # type: ignore[attr-defined]


def test_github_contributors_count_no_link_falls_back_to_len(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(200, json=[{"login": "a"}])

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    cc = client.get_repo_contributors_count("o", "r")  # type: ignore[attr-defined]
    assert cc.count == 1
    client.close()  # type: ignore[attr-defined]


def test_github_latest_release_downloads_sums_assets(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(
            200,
            json={
                "tag_name": "v1.2.3",
                "assets": [{"download_count": 10}, {"download_count": 32}],
            },
        )

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    rel = client.get_latest_release_downloads("cli", "cli")  # type: ignore[attr-defined]
    assert isinstance(rel, _gh.ReleaseDownloads)
    assert rel.total_downloads == 42
    assert rel.tag_name == "v1.2.3"
    client.close()  # type: ignore[attr-defined]


def test_github_search_repos_count_reads_total(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(200, json={"total_count": 5123, "items": []})

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    rsc = client.search_repos_count("language:rust")  # type: ignore[attr-defined]
    assert isinstance(rsc, _gh.RepoSearchCount)
    assert rsc.total_count == 5123
    client.close()  # type: ignore[attr-defined]


def test_github_get_org_repos_returns_response(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(
            200,
            json=[
                {
                    "full_name": "vercel/next.js",
                    "stargazers_count": 120000,
                    "created_at": "2016-10-05T00:00:00Z",
                },
                {"full_name": "vercel/swr", "stargazers_count": 30000},
                {"stargazers_count": 1},  # no full_name → skipped
            ],
        )

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    resp = client.get_org_repos("vercel")  # type: ignore[attr-defined]
    assert isinstance(resp, _gh.GitHubResponse)
    assert len(resp.repos) == 2
    assert resp.repos[0].full_name == "vercel/next.js"
    client.close()  # type: ignore[attr-defined]


def test_github_request_error_is_client_error(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(404, json={"message": "Not Found"})

    client = _mock_client(handler, _gh.GitHubClient, token=None, cache_dir=tmp_path)
    with pytest.raises(_gh.GitHubClientError):
        client.get_org_repos("nope")  # type: ignore[attr-defined]
    client.close()  # type: ignore[attr-defined]


def test_github_last_page_parser_edge_cases() -> None:
    assert _gh._last_page_from_link(None) is None  # pyright: ignore[reportPrivateUsage]
    assert _gh._last_page_from_link('<https://x?page=9>; rel="last"') == 9  # pyright: ignore[reportPrivateUsage]
    assert _gh._last_page_from_link('<https://x?page=2>; rel="next"') is None  # pyright: ignore[reportPrivateUsage]


# --- stack_exchange --------------------------------------------------------


def test_stack_exchange_tag_window_converter_emits_pinned_primitive() -> None:
    window = _se.TagWindowCount(
        tag="rust",
        site="stackoverflow",
        fromdate=1704067200,
        todate=1706745600,
        question_count=850,
    )
    prim = _se.tag_window_to_primitive_yaml(
        window, slug="so-rust-win", concept_slug="rust-adoption", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    _sha_ok(prim)
    unit = prim["unit"]
    assert isinstance(unit, dict) and unit["kind"] == "flow"
    assert prim["value"] == 850.0


def test_stack_exchange_get_tag_questions_in_window_parses_total(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(200, json={"total": 850})

    client = _mock_client(handler, _se.StackExchangeClient, key=None, cache_dir=tmp_path)
    win = client.get_tag_questions_in_window("rust", 1704067200, 1706745600)  # type: ignore[attr-defined]
    assert isinstance(win, _se.TagWindowCount)
    assert win.question_count == 850
    with pytest.raises(_se.StackExchangeClientError):
        client.get_tag_questions_in_window("rust", 2, 1)  # type: ignore[attr-defined]
    client.close()  # type: ignore[attr-defined]


def test_stack_exchange_get_tags_info_batch_returns_response(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(
            200,
            json={
                "items": [
                    {"name": "rust", "count": 42000},
                    {"name": "go", "count": 70000},
                ],
                "has_more": False,
                "quota_remaining": 295,
            },
        )

    client = _mock_client(handler, _se.StackExchangeClient, key=None, cache_dir=tmp_path)
    resp = client.get_tags_info(["rust", "go"])  # type: ignore[attr-defined]
    assert isinstance(resp, _se.StackExchangeResponse)
    assert len(resp.items) == 2
    assert resp.quota_remaining == 295
    with pytest.raises(_se.StackExchangeClientError):
        client.get_tags_info([])  # type: ignore[attr-defined]
    client.close()  # type: ignore[attr-defined]


def test_stack_exchange_get_related_tags_parses(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(200, json={"items": [{"name": "rust-cargo", "count": 1200}]})

    client = _mock_client(handler, _se.StackExchangeClient, key=None, cache_dir=tmp_path)
    related = client.get_related_tags("rust")  # type: ignore[attr-defined]
    assert len(related) == 1
    assert isinstance(related[0], _se.RelatedTag)
    assert related[0].name == "rust-cargo"
    client.close()  # type: ignore[attr-defined]


def test_stack_exchange_request_error_is_client_error(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(500, json={"error": "boom"})

    client = _mock_client(handler, _se.StackExchangeClient, key=None, cache_dir=tmp_path)
    with pytest.raises(_se.StackExchangeClientError):
        client.get_related_tags("rust")  # type: ignore[attr-defined]
    client.close()  # type: ignore[attr-defined]


# --- twitter (converter-only off mocked user-lookup / timeline) ------------


def _tw_user() -> _tw.TwitterUser:
    return _tw.TwitterUser(
        id="2244994945",
        username="OpenAI",
        name="OpenAI",
        followers_count=2_500_000,
        following_count=10,
        tweet_count=1500,
        verified=True,
        created_at="2009-08-10T00:00:00Z",
    )


def test_twitter_tweet_count_and_following_converters() -> None:
    user = _tw_user()
    tc = _tw.tweet_count_to_primitive_yaml(
        user, slug="x-oa-tc", concept_slug="oa", accessed=_accessed()
    )
    fc = _tw.following_count_to_primitive_yaml(
        user, slug="x-oa-fc", concept_slug="oa", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(tc)
    _assert_atomic_primitive_shape(fc)
    _sha_ok(tc)
    _sha_ok(fc)
    assert tc["value"] == 1500.0
    assert fc["value"] == 10.0
    assert tc["source"]["slug"] != fc["source"]["slug"]  # type: ignore[index]


def test_twitter_avg_engagement_from_timeline() -> None:
    tweets = (
        _tw.TwitterTweet(
            id="1", author_id="x", text="a", created_at=None, retweet_count=2, like_count=8
        ),
        _tw.TwitterTweet(
            id="2", author_id="x", text="b", created_at=None, retweet_count=0, like_count=10
        ),
    )
    prim = _tw.avg_engagement_to_primitive_yaml(
        tweets, username="OpenAI", slug="x-oa-eng", concept_slug="oa", accessed=_accessed()
    )
    _assert_atomic_primitive_shape(prim)
    _sha_ok(prim)
    assert prim["value"] == 10.0  # (10 + 10) / 2
    with pytest.raises(_tw.TwitterClientError):
        _tw.avg_engagement_to_primitive_yaml(
            (), username="x", slug="x", concept_slug="x", accessed=_accessed()
        )


def test_twitter_user_lookup_parses_mocked_payload(tmp_path: Path) -> None:
    def handler(request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(
            200,
            json={
                "data": {
                    "id": "1",
                    "username": "OpenAI",
                    "name": "OpenAI",
                    "public_metrics": {
                        "followers_count": 100,
                        "following_count": 5,
                        "tweet_count": 42,
                    },
                    "verified": True,
                    "created_at": "2009-08-10T00:00:00Z",
                }
            },
        )

    client = _mock_client(handler, _tw.TwitterClient, bearer_token="b", cache_dir=tmp_path)
    user = client.user_lookup_by_username("OpenAI")  # type: ignore[attr-defined]
    assert user.tweet_count == 42 and user.following_count == 5
    client.close()  # type: ignore[attr-defined]


def test_twitter_no_paid_endpoints_in_capabilities() -> None:
    """Guard: twitter must expose ONLY the two free-tier endpoints, none paid."""
    specs = _tw.capabilities()
    methods = {s.method for s in specs}
    assert methods == {"user_lookup_by_username", "user_timeline"}
    assert all(s.is_fragile for s in specs)
    assert all(not s.requires_paid_tier for s in specs)


# --- capability counts per connector --------------------------------------


def test_new_connector_capability_counts() -> None:
    assert len(_rd.capabilities()) == 3
    assert len(_gh.capabilities()) == 5
    assert len(_se.capabilities()) == 4
    assert len(_tw.capabilities()) == 2
