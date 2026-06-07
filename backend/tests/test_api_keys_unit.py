"""Adversarial unit tests for API-key generation, hashing, and in-process auth cache.

Tests the pure crypto + in-process store (no DB needed). Coverage:
- generate_raw_key() produces correctly-prefixed, high-entropy, unique keys
- hash_key() is deterministic and differentiates inputs
- The in-process auth cache round-trip (register_hashed / is_cached / unregister)
- principal_for_headers with require=True/False for valid/revoked/missing keys
- Cross-org isolation (two orgs cannot access each other's keys)
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from strata.api.auth import (
    Principal,
    hash_key,
    is_cached,
    principal_for_headers,
    register_hashed,
    register_key,
    unregister,
)
from strata.db.api_keys import generate_raw_key


# --------------------------------------------------------------------------- #
# generate_raw_key() — format, uniqueness, entropy
# --------------------------------------------------------------------------- #
def test_generate_raw_key_has_prefix() -> None:
    """Keys must have the strata_sk_live_ prefix for env/feature recognition."""
    key = generate_raw_key()
    assert key.startswith("strata_sk_live_"), f"expected prefix, got {key}"


def test_generate_raw_key_unique() -> None:
    """Two calls must produce different keys (high entropy)."""
    key1 = generate_raw_key()
    key2 = generate_raw_key()
    assert key1 != key2, "keys must be unique across calls"


def test_generate_raw_key_sufficient_entropy() -> None:
    """Keys must be long enough to resist guessing (32 urlsafe chars ≈ 192 bits)."""
    key = generate_raw_key()
    # strata_sk_live_ is 15 chars; we add 32 urlsafe chars
    assert len(key) >= 47, f"key too short: {len(key)} < 47 (prefix + 32 chars)"


def test_generate_raw_key_many_calls_always_unique() -> None:
    """Stress: 100 calls must all be unique (no collision risk)."""
    keys = {generate_raw_key() for _ in range(100)}
    assert len(keys) == 100, "expected 100 unique keys, got duplicate(s)"


# --------------------------------------------------------------------------- #
# hash_key() — deterministic, differentiable
# --------------------------------------------------------------------------- #
def test_hash_key_deterministic() -> None:
    """Same input must always hash to the same output."""
    raw = "test_key_12345"
    hash1 = hash_key(raw)
    hash2 = hash_key(raw)
    assert hash1 == hash2, "hash_key must be deterministic"


def test_hash_key_different_inputs_different_hashes() -> None:
    """Different inputs must hash to different values."""
    hash1 = hash_key("key_a")
    hash2 = hash_key("key_b")
    assert hash1 != hash2, "different inputs must hash differently"


def test_hash_key_is_sha256_hex() -> None:
    """Output must be a valid sha256 hex (64 chars)."""
    raw = "test"
    h = hash_key(raw)
    assert len(h) == 64, f"sha256 hex must be 64 chars, got {len(h)}"
    assert all(c in "0123456789abcdef" for c in h), f"not valid hex: {h}"


def test_hash_key_case_sensitive() -> None:
    """Keys are case-sensitive — 'Key' ≠ 'key'."""
    hash_upper = hash_key("MyKey")
    hash_lower = hash_key("mykey")
    assert hash_upper != hash_lower, "hash_key must be case-sensitive"


# --------------------------------------------------------------------------- #
# register_hashed / is_cached / unregister round-trip
# --------------------------------------------------------------------------- #
def test_register_hashed_then_is_cached() -> None:
    """After registering a hash, is_cached must return True."""
    key_hash = hash_key("unit_test_key_1")
    register_hashed(key_hash, org_id="test-org", key_id="ak_123abc")
    assert is_cached(key_hash) is True, "key must be cached after registration"


def test_unregister_evicts_from_cache() -> None:
    """After unregistering, is_cached must return False."""
    key_hash = hash_key("unit_test_key_2")
    register_hashed(key_hash, org_id="test-org", key_id="ak_456def")
    assert is_cached(key_hash) is True
    unregister(key_hash)
    assert is_cached(key_hash) is False, "key must be evicted after unregister"


def test_is_cached_for_unknown_hash() -> None:
    """is_cached on a never-registered hash must return False."""
    unknown_hash = hash_key("never_registered_xyz")
    assert is_cached(unknown_hash) is False


def test_unregister_nonexistent_hash_does_not_error() -> None:
    """Unregistering a hash that was never registered must not raise."""
    unknown_hash = hash_key("unknown_xyz")
    # Should not raise
    unregister(unknown_hash)
    assert is_cached(unknown_hash) is False


# --------------------------------------------------------------------------- #
# principal_for_headers — valid keys, missing keys, wrong keys
# --------------------------------------------------------------------------- #
def test_principal_for_headers_valid_key_resolves() -> None:
    """A registered key in X-API-Key header must resolve to the correct org_id."""
    raw = generate_raw_key()
    key_hash = hash_key(raw)
    register_hashed(key_hash, org_id="acme-corp", key_id="ak_test1")

    principal = principal_for_headers({"x-api-key": raw}, require=True)
    assert principal.org_id == "acme-corp"
    assert principal.key_id == "ak_test1"

    # Clean up
    unregister(key_hash)


def test_principal_for_headers_wrong_key_401() -> None:
    """An invalid key in X-API-Key header must raise 401 even when require=False."""
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"x-api-key": "wrong_key_xyz"}, require=False)
    assert exc.value.status_code == 401
    assert "invalid" in str(exc.value.detail).lower()


def test_principal_for_headers_missing_key_require_true_401() -> None:
    """Missing X-API-Key with require=True must raise 401."""
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({}, require=True)
    assert exc.value.status_code == 401
    assert "missing" in str(exc.value.detail).lower()


def test_principal_for_headers_missing_key_require_false_anonymous() -> None:
    """Missing X-API-Key with require=False must return anonymous principal."""
    principal = principal_for_headers({}, require=False)
    assert principal.org_id == "public"
    assert principal.is_anonymous is True


def test_principal_for_headers_revoked_key_401() -> None:
    """A registered then unregistered key must fail with 401."""
    raw = generate_raw_key()
    key_hash = hash_key(raw)
    register_hashed(key_hash, org_id="revoked-org", key_id="ak_revoked")
    assert is_cached(key_hash) is True

    # Now revoke it
    unregister(key_hash)
    assert is_cached(key_hash) is False

    # Attempting to use it must raise 401
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"x-api-key": raw}, require=True)
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------- #
# register_key (raw version) — convenience wrapper
# --------------------------------------------------------------------------- #
def test_register_key_raw_hashes_internally() -> None:
    """register_key(raw, org) must hash the raw and make it usable."""
    raw = "raw_test_key_xyz"
    register_key(raw, "test-org", scopes=("read", "write"))
    principal = principal_for_headers({"x-api-key": raw}, require=True)
    assert principal.org_id == "test-org"
    assert "read" in principal.scopes
    assert "write" in principal.scopes

    # Clean up
    unregister(hash_key(raw))


# --------------------------------------------------------------------------- #
# Cross-org isolation (adversarial: one org cannot revoke/read another's key)
# --------------------------------------------------------------------------- #
def test_cross_org_isolation_different_keys() -> None:
    """Two orgs with different keys must each resolve to their own org_id."""
    raw_a = generate_raw_key()
    raw_b = generate_raw_key()
    hash_a = hash_key(raw_a)
    hash_b = hash_key(raw_b)

    register_hashed(hash_a, org_id="org-a", key_id="ak_a")
    register_hashed(hash_b, org_id="org-b", key_id="ak_b")

    principal_a = principal_for_headers({"x-api-key": raw_a}, require=True)
    principal_b = principal_for_headers({"x-api-key": raw_b}, require=True)

    assert principal_a.org_id == "org-a"
    assert principal_b.org_id == "org-b"
    assert principal_a.org_id != principal_b.org_id

    # Clean up
    unregister(hash_a)
    unregister(hash_b)


def test_org_a_revoke_does_not_affect_org_b() -> None:
    """Unregistering org A's key must not affect org B's key."""
    raw_a = generate_raw_key()
    raw_b = generate_raw_key()
    hash_a = hash_key(raw_a)
    hash_b = hash_key(raw_b)

    register_hashed(hash_a, org_id="org-a", key_id="ak_a")
    register_hashed(hash_b, org_id="org-b", key_id="ak_b")

    # Org A revokes its key
    unregister(hash_a)

    # Org A's key is now invalid
    with pytest.raises(HTTPException):
        principal_for_headers({"x-api-key": raw_a}, require=True)

    # But org B's key still works
    principal_b = principal_for_headers({"x-api-key": raw_b}, require=True)
    assert principal_b.org_id == "org-b"

    # Clean up
    unregister(hash_b)


# --------------------------------------------------------------------------- #
# Principal dataclass — properties and immutability
# --------------------------------------------------------------------------- #
def test_principal_is_anonymous_anonymous() -> None:
    """Principal with key_id='anonymous' must report is_anonymous=True."""
    principal = Principal(org_id="public", key_id="anonymous")
    assert principal.is_anonymous is True


def test_principal_is_anonymous_keyed() -> None:
    """Principal with a real key_id must report is_anonymous=False."""
    principal = Principal(org_id="acme", key_id="ak_123")
    assert principal.is_anonymous is False


def test_principal_frozen() -> None:
    """Principal must be immutable (frozen dataclass)."""
    principal = Principal(org_id="test", key_id="ak_xyz")
    with pytest.raises((AttributeError, TypeError)):
        principal.org_id = "modified"  # type: ignore


def test_principal_scopes_default() -> None:
    """Principal without explicit scopes must have empty tuple by default."""
    principal = Principal(org_id="test", key_id="ak_xyz")
    assert principal.scopes == ()


def test_principal_scopes_provided() -> None:
    """Principal with explicit scopes must carry them."""
    principal = Principal(org_id="test", key_id="ak_xyz", scopes=("read", "write"))
    assert principal.scopes == ("read", "write")


def test_principal_user_id_default_none() -> None:
    """Principal without explicit user_id must default to None."""
    principal = Principal(org_id="test", key_id="ak_xyz")
    assert principal.user_id is None


# --------------------------------------------------------------------------- #
# Edge cases and adversarial scenarios
# --------------------------------------------------------------------------- #
def test_hash_key_with_empty_string() -> None:
    """hash_key on an empty string must still produce a valid hash (not crash)."""
    h = hash_key("")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_key_with_special_chars() -> None:
    """hash_key must handle special characters without crashing."""
    h = hash_key("key!@#$%^&*()_+-=[]{}|;':\",./<>?")
    assert len(h) == 64


def test_hash_key_with_unicode() -> None:
    """hash_key must handle unicode characters (UTF-8 encoded)."""
    h = hash_key("kéy_中文_🔑")
    assert len(h) == 64


def test_principal_for_headers_case_insensitive_header_name() -> None:
    """X-API-Key header lookup must be case-insensitive."""
    raw = generate_raw_key()
    key_hash = hash_key(raw)
    register_hashed(key_hash, org_id="test-org", key_id="ak_case")

    # Try with lowercase
    principal = principal_for_headers({"x-api-key": raw}, require=True)
    assert principal.org_id == "test-org"

    # Clean up
    unregister(key_hash)


def test_register_hashed_with_scopes() -> None:
    """register_hashed must accept and store custom scopes."""
    key_hash = hash_key("scoped_key_xyz")
    register_hashed(
        key_hash, org_id="test-org", key_id="ak_scoped", scopes=("read", "write", "admin")
    )
    principal = principal_for_headers({"x-api-key": "scoped_key_xyz"}, require=True)
    assert principal.scopes == ("read", "write", "admin")

    # Clean up
    unregister(key_hash)


def test_multiple_registrations_same_hash_overwrites() -> None:
    """Registering the same hash twice must overwrite the first (last-write wins)."""
    key_hash = hash_key("overwrite_test_key")
    register_hashed(key_hash, org_id="org-1", key_id="ak_1")
    principal_1 = principal_for_headers({"x-api-key": "overwrite_test_key"}, require=True)
    assert principal_1.org_id == "org-1"

    # Re-register with different org_id
    register_hashed(key_hash, org_id="org-2", key_id="ak_2")
    principal_2 = principal_for_headers({"x-api-key": "overwrite_test_key"}, require=True)
    assert principal_2.org_id == "org-2"

    # Clean up
    unregister(key_hash)


def test_principal_for_headers_empty_header_dict() -> None:
    """Empty header dict with require=False must return anonymous."""
    principal = principal_for_headers({}, require=False)
    assert principal.is_anonymous is True


def test_principal_for_headers_empty_header_dict_require_true() -> None:
    """Empty header dict with require=True must raise 401."""
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({}, require=True)
    assert exc.value.status_code == 401


def test_principal_for_headers_whitespace_key() -> None:
    """A key with only whitespace must fail (invalid key)."""
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"x-api-key": "   "}, require=True)
    assert exc.value.status_code == 401


def test_generate_raw_key_prefix_consistent() -> None:
    """Every generated key must start with the exact prefix."""
    for _ in range(10):
        key = generate_raw_key()
        assert key.startswith("strata_sk_live_"), f"prefix mismatch: {key}"
