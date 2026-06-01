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
    repos: tuple[GitHubRepo, ...]


@dataclass(frozen=True, slots=True)
class ContributorCount:
    full_name: str
    count: int


@dataclass(frozen=True, slots=True)
class ReleaseDownloads:
    full_name: str
    tag_name: str
    total_downloads: int


@dataclass(frozen=True, slots=True)
class RepoSearchCount:
    query: str
    total_count: int


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


def _repo_from_json(raw: dict[str, Any]) -> GitHubRepo:
    created = _parse_iso(raw.get("created_at")) or datetime.now(UTC)
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


def _last_page_from_link(link_header: str | None) -> int | None:
    """Parse the ``page=N`` of the rel="last" entry in a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="last"' not in part:
            continue
        start = part.find("<")
        end = part.find(">", start)
        if start == -1 or end == -1:
            continue
        url = part[start + 1 : end]
        idx = url.find("&page=")
        if idx == -1:
            idx = url.find("?page=")
        if idx == -1:
            continue
        tail = url[idx + len("&page=") :]
        digits = ""
        for ch in tail:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits:
            return int(digits)
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
        return _repo_from_json(raw)

    def _request_list(
        self, path: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        cache_key = json.dumps({"path": path, "params": params or {}, "list": True}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            items = cached.get("items", [])
            return list(items) if isinstance(items, list) else []
        try:
            resp = self._client.get(f"{self.API_BASE}{path}", params=params)
            resp.raise_for_status()
            data: Any = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise GitHubClientError(f"GitHub request failed: {exc}") from exc
        items = data if isinstance(data, list) else []
        self.cache.put(cache_key, {"items": items})
        return items

    def get_repo_contributors_count(self, owner: str, repo: str) -> ContributorCount:
        """Total contributor count via the Link rel=last page number (anon included)."""
        try:
            resp = self._client.get(
                f"{self.API_BASE}/repos/{owner}/{repo}/contributors",
                params={"per_page": "1", "anon": "1"},
            )
            resp.raise_for_status()
            page = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise GitHubClientError(f"GitHub request failed: {exc}") from exc
        last = _last_page_from_link(resp.headers.get("Link"))
        fallback = len(page) if isinstance(page, list) else 0
        count = last if last is not None else fallback
        return ContributorCount(full_name=f"{owner}/{repo}", count=count)

    def get_latest_release_downloads(self, owner: str, repo: str) -> ReleaseDownloads:
        """Sum of asset download counts for the latest release of a repo."""
        raw = self._request(f"/repos/{owner}/{repo}/releases/latest")
        assets = raw.get("assets", []) or []
        total = sum(int(a.get("download_count", 0) or 0) for a in assets)
        return ReleaseDownloads(
            full_name=f"{owner}/{repo}",
            tag_name=str(raw.get("tag_name", "")),
            total_downloads=total,
        )

    def search_repos_count(self, query: str) -> RepoSearchCount:
        """Total repository count matching a code-search query."""
        raw = self._request("/search/repositories", {"q": query, "per_page": "1"})
        return RepoSearchCount(query=query, total_count=int(raw.get("total_count", 0) or 0))

    def get_org_repos(self, org: str, *, per_page: int = 30) -> GitHubResponse:
        """Public repos for an org as a GitHubResponse of GitHubRepo records."""
        clamped = max(1, min(per_page, 100))
        items = self._request_list(f"/orgs/{org}/repos", {"per_page": str(clamped)})
        repos = tuple(_repo_from_json(item) for item in items if item.get("full_name"))
        return GitHubResponse(repos=repos)

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


def _repo_metric_source_yaml(
    repo: GitHubRepo, *, metric: str, value: int, accessed: date
) -> dict[str, Any]:
    payload = json.dumps({"repo": repo.full_name, metric: value}, sort_keys=True)
    return {
        "slug": f"github-{repo.full_name.replace('/', '-').lower()}-{metric}-{accessed.isoformat()}",
        "tier": "community",
        "url": f"https://github.com/{repo.full_name}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def forks_to_primitive_yaml(
    repo: GitHubRepo, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    """Fork-count primitive from the same get_repo fetch (no new HTTP call)."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{repo.full_name} forks (GitHub)",
        "description": f"GitHub fork count for {repo.full_name}. Developer-derivative-work proxy.",
        "value": float(repo.forks_count),
        "unit": {"kind": "stock", "dimension": "events"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": _repo_metric_source_yaml(
            repo, metric="forks", value=repo.forks_count, accessed=accessed
        ),
    }


def watchers_to_primitive_yaml(
    repo: GitHubRepo, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    """Watcher (subscribers) primitive from the same get_repo fetch (no new HTTP call)."""
    if repo.subscribers_count is None:
        raise GitHubClientError(f"{repo.full_name} has no subscribers_count")
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{repo.full_name} watchers (GitHub)",
        "description": (
            f"GitHub watcher (subscriber) count for {repo.full_name}. "
            "Active-interest proxy, distinct from one-time stargazers."
        ),
        "value": float(repo.subscribers_count),
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": _repo_metric_source_yaml(
            repo, metric="watchers", value=repo.subscribers_count, accessed=accessed
        ),
    }


def open_issues_to_primitive_yaml(
    repo: GitHubRepo, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    """Open-issues primitive from the same get_repo fetch (no new HTTP call)."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"{repo.full_name} open issues (GitHub)",
        "description": (
            f"Open issue + PR count for {repo.full_name}. Maintenance-load / activity proxy."
        ),
        "value": float(repo.open_issues_count),
        "unit": {"kind": "stock", "dimension": "events"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": _repo_metric_source_yaml(
            repo, metric="open-issues", value=repo.open_issues_count, accessed=accessed
        ),
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
        CapabilitySpec(
            connector="github",
            method="get_repo_contributors_count",
            description=(
                "Total contributor count (anon included) for a repo, via the "
                "paginated contributors endpoint. Developer-base-size proxy."
            ),
            returns="contributor count for a repo, tier=community",
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
        CapabilitySpec(
            connector="github",
            method="get_latest_release_downloads",
            description=(
                "Summed asset download count for the latest release of a repo. "
                "Distribution / adoption proxy for shipped binaries."
            ),
            returns="release download total for a repo, tier=community",
            args=[
                CapabilityArg(
                    name="owner", type="str", description="Owner / org slug", example="cli"
                ),
                CapabilityArg(
                    name="repo", type="str", description="Repository name", example="cli"
                ),
            ],
            source_tier="community",
        ),
        CapabilitySpec(
            connector="github",
            method="search_repos_count",
            description=(
                "Total number of public repositories matching a search query. "
                "Ecosystem-breadth proxy for a language, topic, or framework."
            ),
            returns="repository match count, tier=community",
            args=[
                CapabilityArg(
                    name="query",
                    type="str",
                    description="GitHub repository search query",
                    example="language:rust stars:>100",
                ),
            ],
            source_tier="community",
        ),
        CapabilitySpec(
            connector="github",
            method="get_org_repos",
            description=(
                "Public repositories for an organization, each with stars / forks / "
                "issues. Org-footprint proxy across an ecosystem owner."
            ),
            returns="GitHubResponse of repo records, tier=community",
            args=[
                CapabilityArg(
                    name="org", type="str", description="Organization slug", example="vercel"
                ),
                CapabilityArg(
                    name="per_page",
                    type="int",
                    description="Max repos (1..100)",
                    example="30",
                    required=False,
                ),
            ],
            source_tier="community",
        ),
    ]
