"""YAML loader. Globs ``data/**/*.yaml`` and dispatches on ``kind`` to the
right Pydantic model.

The loader is intentionally permissive about file location — the slug, not the
path, is the identity. The validator's structural layer enforces slug uniqueness
within record type.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from .models import (
    NON_SIZING_TIERS,
    AnalysisQuestion,
    Annotation,
    AtomicPrimitive,
    CompositePrimitive,
    Concept,
    Framework,
    TAMOutput,
)

# Kinds the loader knows about. Sources are nested inside primitives at v0.2;
# standalone source files act as a curated registry exposed via the source
# record's ``source.snapshot_sha256`` pinning.
KNOWN_KINDS: frozenset[str] = frozenset(
    {
        "atomic_primitive",
        "composite_primitive",
        "concept",
        "framework",
        "annotation",
        "tam_output",
        "analysis_question",
        "source_registry",
        "opt_out_registry",
    }
)


class LoaderError(RuntimeError):
    """One YAML file failed to parse or dispatch."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.detail = message


@dataclass(slots=True)
class LoadedRecords:
    """Output of ``load_data_dir``. The validator consumes this directly."""

    atomic_primitives: list[AtomicPrimitive] = field(default_factory=list[AtomicPrimitive])
    # Signals (e.g. prediction-market probabilities) live under ``data/signals/``.
    # They parse as atomic_primitive YAML but are NEVER sizing-grade inputs: they
    # load here, not into ``atomic_primitives``, and never feed a framework (Q20).
    signals: list[AtomicPrimitive] = field(default_factory=list[AtomicPrimitive])
    composite_primitives: list[CompositePrimitive] = field(default_factory=list[CompositePrimitive])
    concepts: list[Concept] = field(default_factory=list[Concept])
    frameworks: list[Framework] = field(default_factory=list[Framework])
    annotations: list[Annotation] = field(default_factory=list[Annotation])
    tam_outputs: list[TAMOutput] = field(default_factory=list[TAMOutput])
    # Curated analysis-question records (PR4). YAML-only — not a DB table.
    analysis_questions: list[AnalysisQuestion] = field(default_factory=list[AnalysisQuestion])
    # Raw YAML payloads for source / opt-out registries (no Pydantic model yet).
    source_registries: list[tuple[Path, dict[str, Any]]] = field(
        default_factory=list[tuple[Path, dict[str, Any]]]
    )
    opt_out_registries: list[tuple[Path, dict[str, Any]]] = field(
        default_factory=list[tuple[Path, dict[str, Any]]]
    )
    # Raw payloads kept around for validator inspection (e.g. catching scalar
    # defaults in frameworks before Pydantic coerces them).
    raw_by_path: dict[Path, dict[str, Any]] = field(default_factory=dict[Path, dict[str, Any]])


# YAML files that live under ``data/`` but are configuration, not records, and
# must not be parsed by the registry loader (cf. portfolios, kept in a sibling
# dir for the same reason). The ingest manifest is declarative ingest config.
_NON_RECORD_FILENAMES: frozenset[str] = frozenset({"ingest-manifest.yaml"})


def _iter_yaml_files(root: Path) -> Iterable[Path]:
    for ext in ("*.yaml", "*.yml"):
        for path in root.rglob(ext):
            if path.name not in _NON_RECORD_FILENAMES:
                yield path


def load_data_dir(root: Path) -> LoadedRecords:
    """Walk ``root`` and parse every YAML file. Raises on the first failure."""

    if not root.exists():
        raise LoaderError(root, "data directory does not exist")
    signals_root = root / "signals"
    out = LoadedRecords()
    for path in sorted(_iter_yaml_files(root)):
        raw = _read_yaml(path)
        if raw is None:
            continue
        out.raw_by_path[path] = raw
        kind_raw = raw.get("kind")
        if not isinstance(kind_raw, str):
            raise LoaderError(path, "missing or non-string `kind` field")
        if kind_raw not in KNOWN_KINDS:
            raise LoaderError(path, f"unknown kind {kind_raw!r}")
        _dispatch(out, kind_raw, raw, path, is_signal=path.is_relative_to(signals_root))
    return out


def _read_yaml(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LoaderError(path, f"could not read file: {exc}") from exc
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise LoaderError(path, f"YAML parse error: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise LoaderError(path, "top-level YAML must be a mapping")
    return cast(dict[str, Any], parsed)


def _dispatch(
    out: LoadedRecords, kind: str, raw: dict[str, Any], path: Path, *, is_signal: bool = False
) -> None:
    try:
        match kind:
            case "atomic_primitive":
                prim = AtomicPrimitive.model_validate(raw)
                # Quarantine away from the primitive registry (Q20) when EITHER
                # the file lives under data/signals/ OR the record's tier is a
                # non-sizing tier (prediction-market / community-social). The
                # tier check is the load-path-independent guard shared with the
                # DB path — a community/social primitive misfiled under
                # data/primitives/ is still routed to signals, never to a TAM.
                quarantined = is_signal or prim.source.tier in NON_SIZING_TIERS
                (out.signals if quarantined else out.atomic_primitives).append(prim)
            case "composite_primitive":
                out.composite_primitives.append(CompositePrimitive.model_validate(raw))
            case "concept":
                out.concepts.append(Concept.model_validate(raw))
            case "framework":
                out.frameworks.append(Framework.model_validate(raw))
            case "annotation":
                out.annotations.append(Annotation.model_validate(raw))
            case "tam_output":
                out.tam_outputs.append(TAMOutput.model_validate(raw))
            case "analysis_question":
                out.analysis_questions.append(AnalysisQuestion.model_validate(raw))
            case "source_registry":
                out.source_registries.append((path, raw))
            case "opt_out_registry":
                out.opt_out_registries.append((path, raw))
            case _:
                raise LoaderError(path, f"unhandled kind {kind!r}")
    except ValidationError as exc:
        raise LoaderError(path, f"pydantic validation failed: {exc}") from exc
