"""Cached Anthropic client used by Open Org features.

Wraps :class:`anthropic.Anthropic` to standardise prompt caching
(``cache_control={"type": "ephemeral"}``) and surface a typed
:class:`Usage` for downstream cost accounting (:mod:`llmstxt_api.services.llm_usage`).

Pricing-relevant token fields are exposed verbatim from the SDK:
- ``input_tokens`` — uncached input
- ``cache_creation_tokens`` — input contributed to a cache write (~1.25x cost)
- ``cache_read_tokens`` — input served from cache (~0.1x cost)
- ``output_tokens`` — model output

Add new features by passing a ``feature`` label to the caller's logging
hook; this module does not depend on the API DB.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Iterator

from anthropic import Anthropic


DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096


def system_block(text: str, *, cache: bool = False) -> dict:
    """Build an Anthropic system-prompt text block.

    Set ``cache=True`` for stable, long-lived content (theme vocabulary,
    schema requirements, org profile context). The 1024-token minimum for
    Sonnet/Opus prompt caching applies — short blocks will be ignored by
    the cache layer even with this flag set.
    """
    block: dict[str, Any] = {"type": "text", "text": text}
    if cache:
        block["cache_control"] = {"type": "ephemeral"}
    return block


@dataclass
class Usage:
    """Token usage from one Anthropic call.

    Cache fields default to 0 (SDK omits them when caching is not in use).
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = ""

    def billable_input_tokens(self) -> int:
        """Total tokens counted against the input-token cost basis.

        Note this is the *count*, not the cost — pricing tiers for cache
        writes and reads differ from baseline. Use this for telemetry; use
        the API-side cost helper for actual £/$ figures.
        """
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens


@dataclass
class CompletionResult:
    """Result of a synchronous Anthropic completion."""

    text: str
    usage: Usage
    raw: Any = field(repr=False, default=None)


def _usage_from_sdk(response: Any) -> Usage:
    """Extract a :class:`Usage` from an SDK Message response."""
    sdk_usage = response.usage
    return Usage(
        input_tokens=getattr(sdk_usage, "input_tokens", 0) or 0,
        output_tokens=getattr(sdk_usage, "output_tokens", 0) or 0,
        cache_creation_tokens=getattr(sdk_usage, "cache_creation_input_tokens", 0) or 0,
        cache_read_tokens=getattr(sdk_usage, "cache_read_input_tokens", 0) or 0,
        model=getattr(response, "model", "") or "",
    )


def _text_from_blocks(content: list[Any]) -> str:
    """Concatenate text blocks from an SDK response, skipping non-text blocks."""
    return "".join(getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text")


def extract_tool_input(response: Any, tool_name: str) -> dict | None:
    """Return the ``input`` dict of the first ``tool_use`` block matching ``tool_name``.

    Returns ``None`` when the model didn't call the tool. The Open Org theme
    extractor uses this to read structured output without parsing prose.
    """
    content = getattr(response, "content", None) or []
    for block in content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if getattr(block, "name", None) != tool_name:
            continue
        payload = getattr(block, "input", None)
        if isinstance(payload, dict):
            return payload
    return None


class _StreamWrapper(AbstractContextManager):
    """Wraps the SDK stream context manager with our :class:`Usage` accessor."""

    def __init__(self, sdk_cm: Any) -> None:
        self._cm = sdk_cm
        self._sdk_stream: Any = None

    def __enter__(self) -> "_StreamWrapper":
        self._sdk_stream = self._cm.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return self._cm.__exit__(exc_type, exc, tb)

    @property
    def text_stream(self) -> Iterator[str]:
        return self._sdk_stream.text_stream

    def usage(self) -> Usage:
        """Return token usage. Only valid after the stream has been consumed."""
        final = self._sdk_stream.get_final_message()
        return _usage_from_sdk(final)

    def final_text(self) -> str:
        """Return the full concatenated text. Only valid after the stream has been consumed."""
        final = self._sdk_stream.get_final_message()
        return _text_from_blocks(final.content)


class CachedAnthropic:
    """Thin caching-aware wrapper around the sync Anthropic client."""

    def __init__(self, api_key: str, *, default_model: str = DEFAULT_MODEL) -> None:
        self._client = Anthropic(api_key=api_key)
        self.default_model = default_model

    def complete(
        self,
        *,
        messages: list[dict],
        system: str | list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
    ) -> CompletionResult:
        """Synchronous completion.

        Pass ``tools`` and ``tool_choice`` together when you need structured
        output via the Anthropic tool_use API. The raw SDK response is exposed
        on the result; use :func:`extract_tool_input` to pull the tool call out.
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        response = self._client.messages.create(**kwargs)
        return CompletionResult(
            text=_text_from_blocks(response.content),
            usage=_usage_from_sdk(response),
            raw=response,
        )

    def stream(
        self,
        *,
        messages: list[dict],
        system: str | list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
    ) -> _StreamWrapper:
        """Streaming completion.

        Use within a ``with`` block::

            with client.stream(messages=[...]) as stream:
                for delta in stream.text_stream:
                    yield delta
                usage = stream.usage()
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature

        return _StreamWrapper(self._client.messages.stream(**kwargs))


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "CachedAnthropic",
    "CompletionResult",
    "Usage",
    "extract_tool_input",
    "system_block",
]
