"""Unit tests for strata.resolver.llm.

Validates the complete() dispatch logic without making live network or
CLI calls. The STRATA_OFFLINE guard is checked at the top so that CI
skips these tests when the Claude CLI is absent (same convention as
test_goal_pipeline_sse.py).
"""

from __future__ import annotations

import json
import os
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from strata.resolver import llm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_proc(stdout: str, returncode: int = 0, stderr: str = "") -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _cli_envelope(result: str, is_error: bool = False) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": is_error,
            "result": result,
            "session_id": "test-session",
        }
    )


# ---------------------------------------------------------------------------
# CLI backend tests
# ---------------------------------------------------------------------------


@patch("subprocess.run")
def test_complete_cli_returns_result_field(mock_run: MagicMock) -> None:
    """Happy path: valid envelope → returns the result string."""
    mock_run.return_value = _fake_proc(_cli_envelope("hello world"))
    # Ensure ANTHROPIC_API_KEY is absent so the CLI path runs.
    os.environ.pop("ANTHROPIC_API_KEY", None)
    out = llm.complete("test prompt")
    assert out == "hello world"


@patch("subprocess.run")
def test_complete_cli_strips_nothing_itself(mock_run: MagicMock) -> None:
    """complete() returns raw text including fences — callers strip them."""
    fenced = "```json\n{}\n```"
    mock_run.return_value = _fake_proc(_cli_envelope(fenced))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    out = llm.complete("test prompt")
    assert out == fenced


@patch("subprocess.run")
def test_complete_cli_passes_system_arg(mock_run: MagicMock) -> None:
    """--append-system-prompt flag is included when system is given."""
    mock_run.return_value = _fake_proc(_cli_envelope("ok"))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    llm.complete("the prompt", system="be helpful")
    called_args = mock_run.call_args[0][0]
    assert "--append-system-prompt" in called_args
    assert "be helpful" in called_args


@patch("subprocess.run")
def test_complete_cli_raises_on_nonzero_exit(mock_run: MagicMock) -> None:
    mock_run.return_value = _fake_proc("", returncode=1, stderr="something went wrong")
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with pytest.raises(RuntimeError, match="exited with code 1"):
        llm.complete("fail")


@patch("subprocess.run")
def test_complete_cli_raises_on_is_error_true(mock_run: MagicMock) -> None:
    mock_run.return_value = _fake_proc(_cli_envelope("", is_error=True))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with pytest.raises(RuntimeError, match="is_error=true"):
        llm.complete("fail")


@patch("subprocess.run")
def test_complete_cli_raises_on_missing_result(mock_run: MagicMock) -> None:
    # Envelope with no 'result' key at all.
    mock_run.return_value = _fake_proc(json.dumps({"is_error": False}))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with pytest.raises(RuntimeError, match="missing 'result' field"):
        llm.complete("fail")


@patch("subprocess.run")
def test_complete_cli_raises_on_non_json_stdout(mock_run: MagicMock) -> None:
    mock_run.return_value = _fake_proc("not json at all")
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with pytest.raises(RuntimeError, match="non-JSON stdout"):
        llm.complete("fail")


# ---------------------------------------------------------------------------
# SDK fallback tests (ANTHROPIC_API_KEY set)
# ---------------------------------------------------------------------------


def test_complete_uses_sdk_when_api_key_set() -> None:
    """When ANTHROPIC_API_KEY is present the SDK path fires, not subprocess."""
    fake_block = MagicMock()
    fake_block.text = "sdk response"
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    from anthropic.types import TextBlock

    fake_block.__class__ = TextBlock

    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-fake"}, clear=False),
        patch("anthropic.Anthropic") as mock_anthropic_cls,
        patch("subprocess.run") as mock_run,
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        out = llm._complete_sdk(
            "the prompt", system=None, model="claude-sonnet-4-6", max_tokens=256
        )

    assert out == "sdk response"
    mock_run.assert_not_called()


# A stray ANTHROPIC_API_KEY must NOT route the resolver to the API — Claude Code
# is the default; the SDK is an explicit STRATA_LLM_BACKEND=anthropic opt-in.
@patch("subprocess.run")
def test_complete_prefers_cli_even_when_api_key_present(mock_run: MagicMock) -> None:
    mock_run.return_value = _fake_proc(_cli_envelope("from cli"))
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-stray"}, clear=False):
        os.environ.pop("STRATA_LLM_BACKEND", None)
        out = llm.complete("q")
    assert out == "from cli"
    mock_run.assert_called_once()


def test_complete_uses_sdk_when_backend_opts_in() -> None:
    """STRATA_LLM_BACKEND=anthropic routes complete() through the SDK path."""
    with (
        patch.dict("os.environ", {"STRATA_LLM_BACKEND": "anthropic"}, clear=False),
        patch.object(llm, "_complete_sdk", return_value="from sdk") as sdk,
    ):
        out = llm.complete("q")
    assert out == "from sdk"
    sdk.assert_called_once()


def test_complete_sdk_raises_on_non_text_block() -> None:
    """SDK path raises if the response block is not a TextBlock."""
    fake_block = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    with (
        patch("anthropic.Anthropic") as mock_anthropic_cls,
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        with pytest.raises(RuntimeError, match="non-text block"):
            llm._complete_sdk("p", system=None, model="claude-sonnet-4-6", max_tokens=256)
