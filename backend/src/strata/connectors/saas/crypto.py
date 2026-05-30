"""Encrypted, org-scoped OAuth token storage (Wave 5B / AC5B.1).

OAuth access/refresh tokens are secrets — they are stored **encrypted at rest**
(Fernet / AES-128-CBC + HMAC) and scoped to an ``org_id``. The encryption key
comes from ``STRATA_FERNET_KEY`` (a urlsafe base64 32-byte key); in dev/test a
per-process key is generated so nothing runs unencrypted.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from threading import Lock

from cryptography.fernet import Fernet

_log = logging.getLogger(__name__)


def _load_or_make_key() -> bytes:
    raw = os.environ.get("STRATA_FERNET_KEY")
    if raw:
        return raw.encode()
    # Dev/test: ephemeral per-process key — tokens are still never stored in the
    # clear; they just don't survive a restart. Loud about it so a prod deploy
    # that forgot STRATA_FERNET_KEY doesn't silently lose tokens on restart.
    _log.warning(
        "STRATA_FERNET_KEY unset — using an EPHEMERAL key; stored OAuth tokens "
        "will not survive a process restart. Set STRATA_FERNET_KEY in prod."
    )
    return Fernet.generate_key()


_fernet = Fernet(_load_or_make_key())


def encrypt(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode())


def decrypt(token: bytes) -> str:
    return _fernet.decrypt(token).decode()


@dataclass(frozen=True, slots=True)
class StoredToken:
    org_id: str
    provider: str
    ciphertext: bytes

    def reveal(self) -> str:
        return decrypt(self.ciphertext)


class TokenVault:
    """Org-scoped encrypted token store. In-process for tests/single-container;
    the prod table is ``oauth_credentials`` (encrypted column, org_id, RLS)."""

    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], StoredToken] = {}
        self._lock = Lock()

    def store(self, org_id: str, provider: str, access_token: str) -> StoredToken:
        token = StoredToken(org_id, provider, encrypt(access_token))
        with self._lock:
            self._tokens[(org_id, provider)] = token
        return token

    def get(self, org_id: str, provider: str) -> StoredToken | None:
        with self._lock:
            return self._tokens.get((org_id, provider))

    def purge(self, org_id: str, provider: str) -> bool:
        """Remove the org's token for a provider (disconnect). Returns whether
        a token was present."""
        with self._lock:
            return self._tokens.pop((org_id, provider), None) is not None


_vault = TokenVault()


def get_vault() -> TokenVault:
    return _vault


class PendingAuthStore:
    """CSRF defense for the OAuth flow: a random ``state`` is minted at authorize
    and must be echoed back (and consumed once) at callback. Binds the callback
    to the org that started the flow — not to whatever principal hits the
    callback URL."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, str]] = {}
        self._lock = Lock()

    def create(self, org_id: str, provider: str) -> str:
        state = secrets.token_urlsafe(32)
        with self._lock:
            self._pending[state] = (org_id, provider)
        return state

    def consume(self, state: str) -> tuple[str, str] | None:
        """Return (org_id, provider) and invalidate the state (single use)."""
        with self._lock:
            return self._pending.pop(state, None)


_pending_auth = PendingAuthStore()


def get_pending_auth() -> PendingAuthStore:
    return _pending_auth
