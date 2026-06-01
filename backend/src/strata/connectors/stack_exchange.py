"""Stack Exchange connector — tag-volume signals from Stack Overflow + family.

Emits count-unit primitives: questions per tag per period.

API reference: https://api.stackexchange.com/docs
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
class TagInfo:
    name: str
    site: str
    question_count: int
    is_required: bool
    is_moderator_only: bool


@dataclass(frozen=True, slots=True)
class StackExchangeResponse:
    items: tuple[TagInfo, ...]
    has_more: bool
    quota_remaining: int


@dataclass(frozen=True, slots=True)
class TagWindowCount:
    tag: str
    site: str
    fromdate: int
    todate: int
    question_count: int


@dataclass(frozen=True, slots=True)
class RelatedTag:
    name: str
    site: str
    question_count: int


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


class StackExchangeClientError(RuntimeError):
    pass


class StackExchangeClient:
    """Stack Exchange API 2.3 client.

    Key optional (no key: 300 req/day per IP; with key: 10000 req/day).
    """

    API_BASE = "https://api.stackexchange.com/2.3"

    def __init__(
        self,
        key: str | None = None,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.key = key
        self.cache = _DiskCache(cache_dir or Path.home() / ".strata" / "cache" / "stack_exchange")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> StackExchangeClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        signed = dict(params)
        if self.key:
            signed["key"] = self.key
        cache_key = json.dumps({"path": path, "params": params}, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = self._client.get(f"{self.API_BASE}{path}", params=signed)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise StackExchangeClientError(f"Stack Exchange request failed: {exc}") from exc
        self.cache.put(cache_key, data)
        return data

    def get_tag_info(self, tag: str, *, site: str = "stackoverflow") -> TagInfo:
        """Total question count for a tag on a given site."""
        raw = self._request(
            f"/tags/{tag}/info",
            {"site": site, "filter": "default"},
        )
        items = raw.get("items", [])
        if not items:
            raise StackExchangeClientError(f"Tag {tag!r} not found on {site}")
        item = items[0]
        return TagInfo(
            name=str(item.get("name", tag)),
            site=site,
            question_count=int(item.get("count", 0)),
            is_required=bool(item.get("is_required", False)),
            is_moderator_only=bool(item.get("is_moderator_only", False)),
        )

    def get_tags_info(
        self, tags: list[str], *, site: str = "stackoverflow"
    ) -> StackExchangeResponse:
        """Batch tag info for several tags in one /tags/{tags}/info call."""
        if not tags:
            raise StackExchangeClientError("get_tags_info requires at least one tag")
        joined = ";".join(tags)
        raw = self._request(f"/tags/{joined}/info", {"site": site, "filter": "default"})
        items = raw.get("items", []) or []
        infos = tuple(
            TagInfo(
                name=str(item.get("name", "")),
                site=site,
                question_count=int(item.get("count", 0)),
                is_required=bool(item.get("is_required", False)),
                is_moderator_only=bool(item.get("is_moderator_only", False)),
            )
            for item in items
        )
        return StackExchangeResponse(
            items=infos,
            has_more=bool(raw.get("has_more", False)),
            quota_remaining=int(raw.get("quota_remaining", 0)),
        )

    def get_tag_questions_in_window(
        self, tag: str, fromdate: int, todate: int, *, site: str = "stackoverflow"
    ) -> TagWindowCount:
        """Question count for a tag in a [fromdate, todate] unix-second window.

        Uses ``filter=total`` so the response carries only the aggregate count —
        this is the real adoption-trend signal (questions per period).
        """
        if fromdate > todate:
            raise StackExchangeClientError("fromdate must be <= todate")
        raw = self._request(
            "/questions",
            {
                "site": site,
                "tagged": tag,
                "fromdate": str(fromdate),
                "todate": str(todate),
                "filter": "total",
            },
        )
        return TagWindowCount(
            tag=tag,
            site=site,
            fromdate=fromdate,
            todate=todate,
            question_count=int(raw.get("total", 0)),
        )

    def get_related_tags(self, tag: str, *, site: str = "stackoverflow") -> tuple[RelatedTag, ...]:
        """Tags frequently co-occurring with a tag (co-mention graph)."""
        raw = self._request(f"/tags/{tag}/related", {"site": site, "filter": "default"})
        items = raw.get("items", []) or []
        return tuple(
            RelatedTag(
                name=str(item.get("name", "")),
                site=site,
                question_count=int(item.get("count", 0)),
            )
            for item in items
        )

    def clear_cache(self) -> int:
        return self.cache.clear()


def tag_to_primitive_yaml(
    tag: TagInfo, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"Stack Overflow questions tagged [{tag.name}]",
        "description": (
            f"Total question count on {tag.site} for tag '{tag.name}'. Developer-attention proxy."
        ),
        "value": float(tag.question_count),
        "unit": {"kind": "stock", "dimension": "events"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": tag_to_source_yaml(tag, accessed=accessed),
    }


def tag_window_to_primitive_yaml(
    window: TagWindowCount, *, slug: str, concept_slug: str, accessed: date
) -> dict[str, Any]:
    """Questions-per-window primitive — the adoption-trend signal (flow, not stock)."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": f"Stack Overflow questions tagged [{window.tag}] in window",
        "description": (
            f"Question count on {window.site} for tag '{window.tag}' between "
            f"{window.fromdate} and {window.todate} (unix seconds). Adoption-trend proxy."
        ),
        "value": float(window.question_count),
        "unit": {"kind": "flow", "dimension": "events"},
        "as_of": accessed.isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "demand",
        "distribution_shape": "power_law",
        "delivery_mode": "n/a",
        "source": tag_window_to_source_yaml(window, accessed=accessed),
    }


def tag_window_to_source_yaml(window: TagWindowCount, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {
            "tag": window.tag,
            "site": window.site,
            "fromdate": window.fromdate,
            "todate": window.todate,
            "count": window.question_count,
        },
        sort_keys=True,
    )
    return {
        "slug": (
            f"stackexchange-{window.site}-{window.tag}-"
            f"{window.fromdate}-{window.todate}-{accessed.isoformat()}"
        ),
        "tier": "community",
        "url": f"https://{window.site}.com/questions/tagged/{window.tag}",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def tag_to_source_yaml(tag: TagInfo, *, accessed: date) -> dict[str, Any]:
    payload = json.dumps(
        {"tag": tag.name, "site": tag.site, "count": tag.question_count},
        sort_keys=True,
    )
    return {
        "slug": f"stackexchange-{tag.site}-{tag.name}-{accessed.isoformat()}",
        "tier": "community",
        "url": f"https://{tag.site}.com/tags/{tag.name}/info",
        "accessed": accessed.isoformat(),
        "snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }


def capabilities() -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="stack_exchange",
            method="get_tag_info",
            description=(
                "Total question count on a Stack Exchange site for a tag. "
                "Developer-attention / framework adoption proxy."
            ),
            returns="atomic primitive, unit=count, tier=community",
            args=[
                CapabilityArg(
                    name="tag",
                    type="str",
                    description="Tag slug, e.g. 'python', 'react'",
                    example="rust",
                ),
                CapabilityArg(
                    name="site",
                    type="str",
                    description="Stack Exchange site (default stackoverflow)",
                    example="stackoverflow",
                    required=False,
                ),
            ],
            source_tier="community",
        ),
        CapabilitySpec(
            connector="stack_exchange",
            method="get_tag_questions_in_window",
            description=(
                "Question count for a tag within a [fromdate, todate] unix-second "
                "window. The real adoption-trend signal (questions per period)."
            ),
            returns="windowed question count, tier=community",
            args=[
                CapabilityArg(name="tag", type="str", description="Tag slug", example="rust"),
                CapabilityArg(
                    name="fromdate",
                    type="int",
                    description="Window start (unix seconds)",
                    example="1704067200",
                ),
                CapabilityArg(
                    name="todate",
                    type="int",
                    description="Window end (unix seconds)",
                    example="1706745600",
                ),
                CapabilityArg(
                    name="site",
                    type="str",
                    description="Stack Exchange site (default stackoverflow)",
                    example="stackoverflow",
                    required=False,
                ),
            ],
            source_tier="community",
        ),
        CapabilitySpec(
            connector="stack_exchange",
            method="get_tags_info",
            description=(
                "Batch total question counts for several tags in one call. "
                "Cross-technology attention comparison."
            ),
            returns="StackExchangeResponse of tag infos, tier=community",
            args=[
                CapabilityArg(
                    name="tags",
                    type="str",
                    description="Semicolon-separated tag slugs",
                    example="rust;go;zig",
                ),
                CapabilityArg(
                    name="site",
                    type="str",
                    description="Stack Exchange site (default stackoverflow)",
                    example="stackoverflow",
                    required=False,
                ),
            ],
            source_tier="community",
        ),
        CapabilitySpec(
            connector="stack_exchange",
            method="get_related_tags",
            description=(
                "Tags frequently co-occurring with a tag, with their question "
                "counts. Maps the technology-adjacency graph for a topic."
            ),
            returns="tuple of related tags, tier=community",
            args=[
                CapabilityArg(name="tag", type="str", description="Tag slug", example="react"),
                CapabilityArg(
                    name="site",
                    type="str",
                    description="Stack Exchange site (default stackoverflow)",
                    example="stackoverflow",
                    required=False,
                ),
            ],
            source_tier="community",
        ),
    ]
