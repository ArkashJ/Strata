"""Deterministic, dependency-free text embeddings for semantic concept matching.

PR5 (flow 39) adds a semantic-search *fallback* to the resolver: when the
registry-first exact/fuzzy `match_concept` misses, an embedding nearest-neighbour
pass can still recover the concept a free-form query names. Registry-first stays
primary; this only runs on a miss.

The embedding here is an honest **feature-hashing bag-of-words** vector
(a.k.a. the "hashing trick"), NOT a learned LLM embedding:

- Tokenize text → unigrams + bigrams.
- Hash each token (blake2b) into a fixed-dimension bucket; accumulate a signed,
  IDF-free weight per bucket.
- L2-normalize so cosine similarity == dot product.

It is fully deterministic and reproducible (no network, no model download, no
randomness), which matches Strata's provenance-first contract: the same text
always yields the same vector, so a stored embedding can be recomputed and
verified. It captures lexical/term overlap with light n-gram context — enough to
recover "developer tooling market size" → a "dev-tools-tam" concept when the
words differ in order or filler, where the literal fuzzy matcher would miss. It
is intentionally weaker than a transformer embedding; we do not claim semantic
understanding it doesn't have. This stays the FALLBACK, never the primary path.

The vector dimension is fixed at module scope so the pgvector column type
(``vector(EMBED_DIM)``) and the runtime vector always agree.
"""

from __future__ import annotations

import hashlib
import math
import re
from itertools import pairwise

# Fixed embedding dimension. Must equal the pgvector column width in
# migration 010. Changing it requires a migration + `strata embed --rebuild`.
EMBED_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    """Lowercase unigrams plus adjacent bigrams (cheap local context)."""
    words = _TOKEN_RE.findall(text.lower())
    if not words:
        return []
    bigrams = [f"{a}_{b}" for a, b in pairwise(words)]
    return words + bigrams


def _bucket_and_sign(token: str) -> tuple[int, float]:
    """Map a token to a (bucket, sign) pair via a stable hash.

    The signed-hash trick (Weinberger et al.) halves collision bias: two tokens
    landing in the same bucket with opposite signs cancel rather than always
    reinforcing, so unrelated text stays closer to orthogonal.
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    h = int.from_bytes(digest, "big")
    bucket = h % EMBED_DIM
    sign = 1.0 if (h >> 8) & 1 else -1.0
    return bucket, sign


def embed_text(text: str) -> list[float]:
    """Return the L2-normalized feature-hashing embedding of ``text``.

    Empty / token-free text yields the zero vector (its cosine similarity to
    anything is 0, so it never spuriously matches).
    """
    vec = [0.0] * EMBED_DIM
    for token in _tokens(text):
        bucket, sign = _bucket_and_sign(token)
        vec[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (dot product when both are
    L2-normalized; falls back to a guarded form otherwise)."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def concept_embed_text(name: str, definition: str) -> str:
    """The canonical text fed to ``embed_text`` for a concept. Name is weighted
    by repetition so the title dominates the (longer) definition."""
    return f"{name} {name} {definition}"


def primitive_embed_text(name: str, description: str) -> str:
    """The canonical text fed to ``embed_text`` for a primitive."""
    return f"{name} {name} {description}"
