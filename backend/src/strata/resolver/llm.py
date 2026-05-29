"""Thin LLM completion layer for the resolver.

Why this exists: the resolver's LLM calls should work off the developer's
Claude Code subscription (no ANTHROPIC_API_KEY required). We do this by
shelling out to the ``claude`` CLI in headless mode, which authenticates via
the subscription. The Anthropic SDK path is an explicit opt-in for deployments
that prefer a direct API key — it is NOT triggered merely by the presence of
``ANTHROPIC_API_KEY`` (which may exist for other tools).

Backend selection:
  - default                       → Claude Code CLI via ``subprocess.run``
  - STRATA_LLM_BACKEND=anthropic  → Anthropic SDK (direct API call)

The callers are sync; the HTTP layer already wraps them in
``asyncio.to_thread``, so ``subprocess.run`` (blocking) is correct here.
"""

from __future__ import annotations

import json
import os
import subprocess

_DEFAULT_MODEL = "claude-sonnet-4-6"


def complete(
    prompt: str,
    *,
    system: str | None = None,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = 1024,
) -> str:
    """Call the LLM and return the model's raw text response.

    Args:
        prompt:     The user-turn message (what to ask).
        system:     Optional system / role instructions.
        model:      Model ID; defaults to ``claude-sonnet-4-6``.
        max_tokens: Upper bound on response length (only honoured by the
                    SDK path; the CLI ignores it but we accept the arg for
                    a uniform signature).

    Returns:
        The model's answer as a plain string (markdown fences NOT stripped
        here — callers handle that via their own ``_strip_code_fence``).

    Raises:
        RuntimeError: on non-zero CLI exit, ``is_error: true`` in the
                      envelope, or a missing ``result`` field.
    """
    # Claude Code is the default (the user's explicit choice). Use the Anthropic
    # SDK ONLY when opted in via STRATA_LLM_BACKEND=anthropic — so a stray or
    # low-credit ANTHROPIC_API_KEY that happens to be in the environment (e.g.
    # for some other tool) never silently hijacks the resolver.
    if os.environ.get("STRATA_LLM_BACKEND", "").strip().lower() == "anthropic":
        return _complete_sdk(prompt, system=system, model=model, max_tokens=max_tokens)
    return _complete_cli(prompt, system=system, model=model)


# ---------------------------------------------------------------------------
# Claude Code CLI backend (default)
# ---------------------------------------------------------------------------


def _complete_cli(
    prompt: str,
    *,
    system: str | None,
    model: str,
) -> str:
    """Shell out to the ``claude`` CLI in headless / non-interactive mode."""
    args = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--disallowed-tools",
        "*",
    ]
    if system:
        args += ["--append-system-prompt", system]

    # Close stdin: the prompt is passed as an arg, so the CLI must not block
    # waiting for piped input (otherwise it warns "no stdin data received" and
    # exits non-zero in a non-interactive subprocess).
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL
    )

    if proc.returncode != 0:
        # The CLI usually reports the real cause (e.g. "Credit balance is too
        # low") in its JSON stdout even on a non-zero exit. Prefer that over an
        # empty stderr so the failure is diagnosable instead of opaque.
        detail = proc.stderr.strip() if proc.stderr else ""
        if not detail and proc.stdout:
            try:
                env = json.loads(proc.stdout)
                detail = str(env.get("result") or env.get("error") or "")
            except json.JSONDecodeError:
                detail = proc.stdout[:400]
        raise RuntimeError(
            f"claude CLI exited with code {proc.returncode}: {detail or '<no output>'}"
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude CLI returned non-JSON stdout: {proc.stdout[:400]!r}") from exc

    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI reported is_error=true: {envelope}")

    result = envelope.get("result")
    if result is None:
        raise RuntimeError(f"claude CLI envelope missing 'result' field: {envelope}")

    return str(result)


# ---------------------------------------------------------------------------
# Anthropic SDK backend (used when ANTHROPIC_API_KEY is set)
# ---------------------------------------------------------------------------


def _complete_sdk(
    prompt: str,
    *,
    system: str | None,
    model: str,
    max_tokens: int,
) -> str:
    """Direct API call via the Anthropic SDK.  Used in production."""
    import anthropic
    from anthropic.types import TextBlock

    client = anthropic.Anthropic()
    messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": prompt}]
    if system:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
    else:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise RuntimeError("Anthropic SDK returned a non-text block")
    return block.text
