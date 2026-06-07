"""Trusted-host allowlist for OAuth ``redirect_uri`` validation (KTD-6).

ChatGPT's production callback path is **dynamic per connector**
(``https://chatgpt.com/connector/oauth/{callback_id}``), so a hardcoded
full-URL allowlist cannot work. The control is two-layered:

1. ``/oauth/authorize`` requires the incoming ``redirect_uri`` to **exact-match**
   one the client persisted via DCR (RFC 6749 exact match).
2. ``is_trusted_redirect_uri`` here gates the scheme+host so a client cannot
   register — and then be redirected to — an attacker-controlled host
   (open-redirect defense in depth).

Trusted: ``https`` to ``claude.ai`` / ``chatgpt.com`` / ``chat.openai.com``, and
RFC 8252 loopback (``http`` to ``127.0.0.1`` / ``[::1]`` / ``localhost``, any
port) for Claude Code's local callback. Everything else is rejected.
"""

from __future__ import annotations

from urllib.parse import urlsplit

# Exact hosts allowed over https (no port — these are public endpoints on 443).
_TRUSTED_HTTPS_HOSTS = frozenset(
    {
        "claude.ai",
        "chatgpt.com",
        "chat.openai.com",
    }
)
# Loopback hosts allowed over http on any port (RFC 8252 native-app redirect).
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_trusted_redirect_uri(uri: str) -> bool:
    """True iff ``uri``'s scheme+host is on the trusted-host allowlist.

    Rejects anything unparseable, any non-https public host, and any http host
    that is not loopback. Userinfo (``user:pass@``) is rejected outright — a
    trusted host in the userinfo with an attacker host as the real host
    (``https://claude.ai@evil.test/``) must not pass."""
    try:
        parts = urlsplit(uri)
    except ValueError:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    if parts.scheme == "https":
        return host in _TRUSTED_HTTPS_HOSTS
    if parts.scheme == "http":
        return host in _LOOPBACK_HOSTS
    return False
