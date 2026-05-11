"""Chat-creator conversation orchestrator.

Wires the prompt files, the theme vocabulary, the optional org-profile
context, and the ``update_current_markdown`` tool into one call to
``CachedAnthropic.stream``. The caller iterates ``turn.text_stream`` for the
assistant's prose and reads ``turn.final_markdown()``/``turn.usage()`` after
the stream finishes.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from llmstxt_core.llm import (
    CachedAnthropic,
    Usage,
    extract_tool_input,
    system_block,
)
from llmstxt_core.open_org.theme_extractor import _vocabulary_block_text


CreatorKind = Literal["strategy", "idea"]

UPDATE_TOOL_NAME = "update_current_markdown"

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_VALID_KINDS = ("strategy", "idea")


@lru_cache(maxsize=4)
def load_prompt(kind: str) -> str:
    """Return the system-prompt text for ``kind`` from disk (cached)."""
    if kind not in _VALID_KINDS:
        raise ValueError(f"unknown kind: {kind!r}; expected one of {_VALID_KINDS}")
    path = _PROMPT_DIR / f"{kind}.md"
    return path.read_text(encoding="utf-8")


def _build_tool_spec() -> dict:
    return {
        "name": UPDATE_TOOL_NAME,
        "description": (
            "Replace the live preview with the current best draft of the "
            "strategy or idea markdown, including the YAML frontmatter. "
            "Call this after each user turn, even if the document is still "
            "incomplete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "markdown": {
                    "type": "string",
                    "description": "Full markdown document with YAML frontmatter.",
                }
            },
            "required": ["markdown"],
        },
    }


def _build_system_blocks(
    *,
    kind: CreatorKind,
    org_profile_summary: str | None,
) -> list[dict]:
    blocks: list[dict] = [
        system_block(load_prompt(kind), cache=True),
        system_block(_vocabulary_block_text(), cache=True),
    ]
    if org_profile_summary:
        blocks.append(
            system_block(
                "Organisation context (use to keep the conversation grounded):\n"
                + org_profile_summary
            )
        )
    return blocks


# ---------------------------------------------------------------------------
# Turn wrapper
# ---------------------------------------------------------------------------


class _CreatorTurn(AbstractContextManager):
    """Wraps an in-flight SDK stream and exposes derived state."""

    def __init__(self, sdk_stream_cm: Any) -> None:
        self._cm = sdk_stream_cm
        self._sdk_stream: Any = None

    def __enter__(self) -> "_CreatorTurn":
        self._sdk_stream = self._cm.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return self._cm.__exit__(exc_type, exc, tb)

    @property
    def text_stream(self):
        return self._sdk_stream.text_stream

    def final_markdown(self) -> str | None:
        """Return the last ``update_current_markdown`` argument, if any.

        Only call after the text stream has been exhausted.
        """
        final = self._sdk_stream.get_final_message()
        payload = extract_tool_input(final, UPDATE_TOOL_NAME)
        if not payload:
            return None
        md = payload.get("markdown")
        return md if isinstance(md, str) else None

    def usage(self) -> Usage:
        """Token usage for this turn. Only valid after the stream is consumed."""
        final = self._sdk_stream.get_final_message()
        sdk_usage = final.usage
        return Usage(
            input_tokens=getattr(sdk_usage, "input_tokens", 0) or 0,
            output_tokens=getattr(sdk_usage, "output_tokens", 0) or 0,
            cache_creation_tokens=getattr(sdk_usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(sdk_usage, "cache_read_input_tokens", 0) or 0,
            model=getattr(final, "model", "") or "",
        )


def start_turn(
    *,
    client: CachedAnthropic,
    kind: CreatorKind,
    conversation_history: list[dict],
    user_message: str,
    org_profile_summary: str | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
) -> _CreatorTurn:
    """Start a streaming turn. Returns a context manager around the stream.

    Use within a ``with`` block::

        with start_turn(client=..., kind="strategy", ...) as turn:
            for chunk in turn.text_stream:
                ...
            md = turn.final_markdown()
            usage = turn.usage()
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"unknown kind: {kind!r}")

    messages = list(conversation_history) + [
        {"role": "user", "content": user_message}
    ]
    system = _build_system_blocks(kind=kind, org_profile_summary=org_profile_summary)

    sdk_cm = client._client.messages.stream(
        model=model or client.default_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        tools=[_build_tool_spec()],
    )
    return _CreatorTurn(sdk_cm)


__all__ = [
    "UPDATE_TOOL_NAME",
    "CreatorKind",
    "load_prompt",
    "start_turn",
]
