"""GitHub connector — community-tier developer signals.

PAT auth (or unauthenticated for low rate-limited calls). Emits count-unit
primitives: repo stars, contributors, languages used.

API reference: https://docs.github.com/en/rest
"""

from __future__ import annotations

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
class GitHubRepo:
    full_name: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    subscribers_count: int | None
    language: str | None
    created_at: datetime
    pushed_at: datetime | None


@dataclass(frozen=True, slots=True)
class GitHubResponse:
    repo: GitHubRepo


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


class GitHubClientError(RuntimeError):
    pass


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubClient:
    """GitHub REST v3 client.

    PAT optional but recommended (unauth: 60 req/h; PAT: 5000 req/h).
    """

    API_BASE = "https://api.github.com"
    USER_AGENT = "strata/0.3"

    def __init__(
        self,
        token: str | None = None,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.token = token
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "github")
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        cache_key = json.dumps({"path": path, "params": params or {}}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = self._client.get(f"{self.API_BASE}{path}", params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise GitHubClientError(f"GitHub request failed: {exc}") from exc
        self.cache.put(cache_key, data)
        return data

    def get_repo(self, owner: str, repo: str) -> GitHubRepo:
        """Stars, forks, issues, language for a public repo."""
        raw = self._request(f"/repos/{owner}/{repo}")
        if not raw or "full_name" not in raw:
            raise GitHubClientError(f"Repo {owner}/{repo} not found")
        created = _parse_iso(raw.get("created_at"))
        if created is None:
            created = datetime.now(UTC)
        return GitHubRepo(
            full_name=str(raw["full_name"]),
            stargazers_count=int(raw.get("stargazers_count", 0)),
            forks_count=int(raw.get("forks_count", 0)),
            open_issues_count=int(raw.get("open_issues_count", 0)),
            subscribers_count=int(raw["subscribers_count"])
            if raw.get("subscribers_count") is not None
            else None,
            language=str(raw["language"]) if raw.get("language") else None,
            created_at=created,
            pushed_at=_parse_iso(raw.get("pushed_at")),
        )

    def clear_cache(self) -> int:
        return self.cache.clear()


def repo_to_primitive_yaml(
    repo: GitHubRepo, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{repo.full_name} stargazers (GitHub)",
        "description": (f"GitHub star count for {repo.full_name}. Developer-interest proxy."),
        "value": float(repo.stargazers_count),
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": repo_to_source_yaml(repo, accessed=accessed),
    }


def repo_to_source_yaml(repo: GitHubRepo, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps({"repo": repo.full_name, "stars": repo.stargazers_count}, sort_keys=True)
    return {
        "slug": f"github-{repo.full_name.replace('/', '-').lower()}-{accessed.isoformat()}",
        "tier": "community",
        "url": f"https://github.com/{repo.full_name}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="github",
            method="get_repo",
            description=(
                "GitHub stars, forks, open-issues count for a public repo. "
                "Developer-interest signal; use as latent-demand proxy."
            ),
            returns="atomic primitive, unit=count, tier=community",
            args=[
                CapabilityArg(
                    name="owner", type="str", description="Owner / org slug", example="vercel"
                ),
                CapabilityArg(
                    name="repo", type="str", description="Repository name", example="next.js"
                ),
            ],
            source_tier="community",
        ),
    ]
