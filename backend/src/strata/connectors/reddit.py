"""Reddit connector — community-tier subreddit signals.

Emits count-unit primitives (subscribers, active users, recent posts/day).
Not a $-denominated source — useful as a latent-demand proxy only.

OAuth via Reddit's app-only credentials endpoint. We do not require ``praw``;
the bare HTTP API is sufficient for the read-only methods we expose.

API reference: https://www.reddit.com/dev/api
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from ._capability import CapabilityArg, CapabilitySpec


@dataclass(frozen=True, slots=True)
class SubredditStats:
    name: str
    subscribers: int
    active_user_count: int | None
    created_utc: datetime
    public_description: str
    over_18: bool


@dataclass(frozen=True, slots=True)
class RedditResponse:
    items: tuple[SubredditStats, ...]


class _DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 3600) -> None:
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


class RedditClientError(RuntimeError):
    pass


class RedditClient:
    """Reddit OAuth client, app-only flow.

    Requires ``client_id`` + ``client_secret`` from a registered Reddit app.
    """

    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    API_BASE = "https://oauth.reddit.com"
    USER_AGENT = "strata/0.3 (market sizing)"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not client_id or not client_secret:
            raise RedditClientError("Reddit client_id and client_secret required")
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "reddit")
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": self.USER_AGENT})
        self._token: str | None = None
        self._token_expires: float = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RedditClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _get_token(self) -> str:
        if self._token is not None and time.time() < self._token_expires - 60:
            return self._token
        creds = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        try:
            resp = self._client.post(
                self.TOKEN_URL,
                headers={"Authorization": f"Basic {creds}"},
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise RedditClientError(f"Reddit token request failed: {exc}") from exc
        token = str(payload.get("access_token", ""))
        if not token:
            raise RedditClientError("Reddit token response missing access_token")
        self._token = token
        self._token_expires = time.time() + float(payload.get("expires_in", 3600))
        return token

    def _request(self, path: str) -> dict[str, Any]:
        cache_key = json.dumps({"path": path}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        token = self._get_token()
        try:
            resp = self._client.get(
                f"{self.API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise RedditClientError(f"Reddit request failed: {exc}") from exc
        self.cache.put(cache_key, data)
        return data

    def get_subreddit_about(self, subreddit: str) -> SubredditStats:
        """Subscriber count, active users, description for a subreddit."""
        raw = self._request(f"/r/{subreddit}/about")
        data = raw.get("data", {})
        if not data:
            raise RedditClientError(f"No subreddit {subreddit!r}")
        return SubredditStats(
            name=str(data.get("display_name", subreddit)),
            subscribers=int(data.get("subscribers", 0)),
            active_user_count=int(data["active_user_count"])
            if data.get("active_user_count") is not None
            else None,
            created_utc=datetime.fromtimestamp(int(data.get("created_utc", time.time())), tz=UTC),
            public_description=str(data.get("public_description", "")),
            over_18=bool(data.get("over18", False)),
        )

    def clear_cache(self) -> int:
        return self.cache.clear()


def subreddit_to_primitive_yaml(
    stats: SubredditStats, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"r/{stats.name} subscribers (Reddit)",
        "description": (
            f"Subscriber count on r/{stats.name}. Community signal — useful as a "
            "latent-demand proxy, not a $-denominated measure."
        ),
        "value": float(stats.subscribers),
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": subreddit_to_source_yaml(stats, accessed=accessed),
    }


def subreddit_to_source_yaml(stats: SubredditStats, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {"subreddit": stats.name, "subscribers": stats.subscribers}, sort_keys=True
    )
    return {
        "slug": f"reddit-{stats.name.lower()}-{accessed.isoformat()}",
        "tier": "community",
        "url": f"https://www.reddit.com/r/{stats.name}/about.json",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="reddit",
            method="get_subreddit_about",
            description=(
                "Subscriber count + active users for a subreddit. Community "
                "signal — useful for latent-demand proxies, not $-sizing."
            ),
            returns="atomic primitive, unit=count people, tier=community",
            args=[
                CapabilityArg(
                    name="subreddit",
                    type="str",
                    description="Subreddit name without /r/ prefix",
                    example="MachineLearning",
                ),
            ],
            source_tier="community",
        ),
    ]
