"""Twitter / X connector — restricted to the 2 free-tier endpoints that work.

Per spec §4, the free X API only meaningfully supports:
  - ``user_lookup_by_username`` — follower count, public profile
  - ``user_timeline``           — rate-limited but free

Search and tweet-volume endpoints are intentionally NOT included; their
capability specs would have to set ``requires_paid_tier=True`` and the
router would never pick them on a free-tier key. Per audit fix F we do
not ship dead-code stubs for them.

API reference: https://developer.x.com/en/docs/twitter-api
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from ._capability import CapabilityArg, CapabilitySpec


@dataclass(frozen=True, slots=True)
class TwitterUser:
    id: str
    username: str
    name: str
    followers_count: int
    following_count: int
    tweet_count: int
    verified: bool
    created_at: str | None


@dataclass(frozen=True, slots=True)
class TwitterTweet:
    id: str
    author_id: str
    text: str
    created_at: str | None
    retweet_count: int
    like_count: int


@dataclass(frozen=True, slots=True)
class TwitterResponse:
    user: TwitterUser | None
    tweets: tuple[TwitterTweet, ...] = ()


class _DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
        self.directory = directory
        self.ttl = ttl_seconds
        directory.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def get(self, params: str) -> dict[str, Any] | None:
        path = self.directory / f"{self._key(params)}.json"
        if not path.exists() or time.time() - path.stat().st_mtime > self.ttl:
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def put(self, params: str, data: dict[str, Any]) -> None:
        (self.directory / f"{self._key(params)}.json").write_text(json.dumps(data))

    def clear(self) -> int:
        count = 0
        for p in self.directory.glob("*.json"):
            p.unlink()
            count += 1
        return count


class TwitterClientError(RuntimeError):
    pass


class TwitterClient:
    """X v2 client. Bearer-token auth.

    Only the two endpoints that work on the free tier are exposed.
    """

    API_BASE = "https://api.twitter.com/2"

    def __init__(
        self,
        bearer_token: str,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not bearer_token:
            raise TwitterClientError("Twitter bearer token required")
        self.bearer_token = bearer_token
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "twitter")
        self._client = httpx.Client(
            timeout=timeout, headers={"Authorization": f"Bearer {bearer_token}"}
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TwitterClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        cache_key = json.dumps({"path": path, "params": params}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = self._client.get(f"{self.API_BASE}{path}", params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise TwitterClientError(f"Twitter request failed: {exc}") from exc
        self.cache.put(cache_key, data)
        return data

    def user_lookup_by_username(self, username: str) -> TwitterUser:
        """Followers, following, tweet count, verified flag for a username."""
        raw = self._request(
            f"/users/by/username/{username}",
            {
                "user.fields": "public_metrics,verified,created_at",
            },
        )
        data = raw.get("data")
        if not data:
            raise TwitterClientError(f"User {username!r} not found")
        metrics = data.get("public_metrics", {})
        return TwitterUser(
            id=str(data["id"]),
            username=str(data.get("username", username)),
            name=str(data.get("name", "")),
            followers_count=int(metrics.get("followers_count", 0)),
            following_count=int(metrics.get("following_count", 0)),
            tweet_count=int(metrics.get("tweet_count", 0)),
            verified=bool(data.get("verified", False)),
            created_at=str(data["created_at"]) if data.get("created_at") else None,
        )

    def user_timeline(self, user_id: str, *, max_results: int = 10) -> tuple[TwitterTweet, ...]:
        """Recent tweets for a user_id (rate-limited but free).

        Per spec §4, this is the second of the two endpoints reliably available
        on the X free tier. Caller passes a user_id (from ``user_lookup_by_username``).
        """
        clamped = max(5, min(max_results, 100))
        raw = self._request(
            f"/users/{user_id}/tweets",
            {
                "max_results": str(clamped),
                "tweet.fields": "created_at,public_metrics",
            },
        )
        items = raw.get("data", []) or []
        tweets: list[TwitterTweet] = []
        for item in items:
            metrics = item.get("public_metrics", {}) or {}
            tweets.append(
                TwitterTweet(
                    id=str(item.get("id", "")),
                    author_id=str(user_id),
                    text=str(item.get("text", "")),
                    created_at=str(item["created_at"]) if item.get("created_at") else None,
                    retweet_count=int(metrics.get("retweet_count", 0)),
                    like_count=int(metrics.get("like_count", 0)),
                )
            )
        return tuple(tweets)

    def clear_cache(self) -> int:
        return self.cache.clear()


def user_to_primitive_yaml(
    user: TwitterUser, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"@{user.username} followers (X)",
        "description": (f"X follower count for @{user.username}. Public-attention proxy."),
        "value": float(user.followers_count),
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": user_to_source_yaml(user, accessed=accessed),
    }


def user_to_source_yaml(user: TwitterUser, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {"username": user.username, "followers": user.followers_count}, sort_keys=True
    )
    return {
        "slug": f"twitter-{user.username.lower()}-{accessed.isoformat()}",
        "tier": "analyst",
        "url": f"https://x.com/{user.username}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="twitter",
            method="user_lookup_by_username",
            description=(
                "Follower count, tweet count, verified status for an X (Twitter) "
                "username. Public-attention proxy; only endpoint reliable on the "
                "free X API tier."
            ),
            returns="atomic primitive, unit=count people, tier=analyst",
            args=[
                CapabilityArg(
                    name="username",
                    type="str",
                    description="X handle without @",
                    example="OpenAI",
                ),
            ],
            source_tier="analyst",
            is_fragile=True,
        ),
        CapabilitySpec(
            connector="twitter",
            method="user_timeline",
            description=(
                "Recent public tweets for a user_id (rate-limited but free on "
                "the X free tier). Returns engagement counts (likes/RTs) per tweet."
            ),
            returns="tuple of tweet metadata; not directly a primitive",
            args=[
                CapabilityArg(
                    name="user_id",
                    type="str",
                    description="X numeric user id (from user_lookup_by_username)",
                    example="2244994945",
                ),
                CapabilityArg(
                    name="max_results",
                    type="int",
                    description="Number of tweets to fetch (5..100)",
                    example="10",
                    required=False,
                ),
            ],
            source_tier="analyst",
            is_fragile=True,
        ),
    ]
