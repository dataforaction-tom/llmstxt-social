"""Multi-provider LLM clients sharing one provider-neutral surface.

The Open Org features were originally written against Anthropic's SDK
(:class:`llmstxt_core.llm.CachedAnthropic`). This module adds an
OpenAI-compatible client so the same call sites can run against **OpenRouter**
or **Ollama Cloud** — both speak the OpenAI chat-completions API and differ only
by base URL, key, and model id.

All clients return the same :class:`~llmstxt_core.llm.CompletionResult` /
:class:`~llmstxt_core.llm.Usage`, and tool calls are normalised onto the result
(:meth:`CompletionResult.tool_input`) so consumers never touch a provider's raw
response shape. Select a client at runtime with :func:`build_llm_client`.

Anthropic-specific prompt caching (``cache_control``) has no equivalent on the
OpenAI-compatible providers — OpenRouter caches automatically for supported
models and Ollama caches locally — so the adapter flattens Anthropic-style
system blocks into a single plain system message and drops ``cache_control``.
"""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import Any, Iterator

from openai import OpenAI

from llmstxt_core.llm import (
    CachedAnthropic,
    CompletionResult,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    ToolCall,
    Usage,
)


# Default endpoints. Both accept an OpenAI-compatible /chat/completions API.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL = "https://ollama.com/v1"


# ---------------------------------------------------------------------------
# Anthropic-shape -> OpenAI-shape translation
# ---------------------------------------------------------------------------


def _system_to_text(system: str | list[dict] | None) -> str | None:
    """Flatten an Anthropic ``system`` (str or list of text blocks) to a string.

    ``cache_control`` and other Anthropic-only block keys are dropped — the
    OpenAI-compatible providers handle caching themselves.
    """
    if system is None:
        return None
    if isinstance(system, str):
        return system
    parts = [
        block.get("text", "")
        for block in system
        if isinstance(block, dict) and block.get("type", "text") == "text"
    ]
    return "\n\n".join(p for p in parts if p)


def _tools_to_openai(tools: list[dict] | None) -> list[dict] | None:
    """Translate Anthropic tool specs to OpenAI ``function`` tool specs."""
    if not tools:
        return None
    out: list[dict] = []
    for tool in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object"}),
                },
            }
        )
    return out


def _tool_choice_to_openai(tool_choice: dict | None) -> Any:
    """Translate an Anthropic ``tool_choice`` to the OpenAI equivalent."""
    if tool_choice is None:
        return None
    kind = tool_choice.get("type")
    if kind == "tool" and tool_choice.get("name"):
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    if kind == "any":
        return "required"
    if kind == "auto":
        return "auto"
    return None


def _build_messages(system: str | list[dict] | None, messages: list[dict]) -> list[dict]:
    system_text = _system_to_text(system)
    if system_text is None:
        return list(messages)
    return [{"role": "system", "content": system_text}, *messages]


def _usage_from_openai(response: Any) -> Usage:
    sdk_usage = getattr(response, "usage", None)
    if sdk_usage is None:
        return Usage(model=getattr(response, "model", "") or "")
    details = getattr(sdk_usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0 if details is not None else 0
    return Usage(
        input_tokens=getattr(sdk_usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(sdk_usage, "completion_tokens", 0) or 0,
        cache_read_tokens=cached,
        model=getattr(response, "model", "") or "",
    )


def _tool_calls_from_openai(message: Any) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for call in getattr(message, "tool_calls", None) or []:
        fn = getattr(call, "function", None)
        if fn is None:
            continue
        name = getattr(fn, "name", None)
        raw_args = getattr(fn, "arguments", None)
        if not isinstance(name, str):
            continue
        try:
            parsed = json.loads(raw_args) if raw_args else {}
        except (TypeError, ValueError):
            parsed = {}
        if isinstance(parsed, dict):
            calls.append(ToolCall(name=name, input=parsed))
    return calls


# ---------------------------------------------------------------------------
# Streaming wrapper
# ---------------------------------------------------------------------------


class _OpenAIStreamWrapper(AbstractContextManager):
    """Provider-neutral stream wrapper around an OpenAI streaming response.

    Mirrors :class:`llmstxt_core.llm._StreamWrapper`: iterate ``text_stream``
    to drain the assistant's prose, then read ``final_tool_input`` / ``usage``.
    Tool-call argument fragments and the trailing usage chunk are accumulated as
    the stream is consumed.
    """

    def __init__(self, sdk_stream: Any) -> None:
        self._sdk_stream = sdk_stream
        self._text_parts: list[str] = []
        self._tool_args: dict[int, dict[str, str]] = {}
        self._usage: Usage = Usage()
        self._consumed = False

    def __enter__(self) -> "_OpenAIStreamWrapper":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        close = getattr(self._sdk_stream, "close", None)
        if close is not None:
            close()
        return False

    @property
    def text_stream(self) -> Iterator[str]:
        for chunk in self._sdk_stream:
            if getattr(chunk, "usage", None):
                self._usage = _usage_from_openai(chunk)
            for choice in getattr(chunk, "choices", None) or []:
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    self._text_parts.append(content)
                    yield content
                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc, "index", 0) or 0
                    slot = self._tool_args.setdefault(idx, {"name": "", "args": ""})
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["args"] += fn.arguments
        self._consumed = True

    def final_text(self) -> str:
        return "".join(self._text_parts)

    def final_tool_input(self, name: str) -> dict | None:
        for slot in self._tool_args.values():
            if slot.get("name") != name:
                continue
            try:
                parsed = json.loads(slot["args"]) if slot["args"] else {}
            except (TypeError, ValueError):
                return None
            return parsed if isinstance(parsed, dict) else None
        return None

    def usage(self) -> Usage:
        return self._usage


# ---------------------------------------------------------------------------
# OpenAI-compatible client
# ---------------------------------------------------------------------------


class OpenAICompatibleClient:
    """LLM client for OpenRouter / Ollama Cloud (OpenAI chat-completions API).

    Presents the same surface as :class:`llmstxt_core.llm.CachedAnthropic`
    (``complete`` / ``stream`` / ``default_model``) so call sites are
    provider-agnostic.
    """

    def __init__(self, api_key: str, base_url: str, *, default_model: str = DEFAULT_MODEL) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
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
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": _build_messages(system, messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        translated_tools = _tools_to_openai(tools)
        if translated_tools is not None:
            kwargs["tools"] = translated_tools
        translated_choice = _tool_choice_to_openai(tool_choice)
        if translated_choice is not None:
            kwargs["tool_choice"] = translated_choice

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        return CompletionResult(
            text=getattr(message, "content", None) or "",
            usage=_usage_from_openai(response),
            raw=response,
            tool_calls=_tool_calls_from_openai(message),
        )

    def stream(
        self,
        *,
        messages: list[dict],
        system: str | list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> _OpenAIStreamWrapper:
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": _build_messages(system, messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        translated_tools = _tools_to_openai(tools)
        if translated_tools is not None:
            kwargs["tools"] = translated_tools

        sdk_stream = self._client.chat.completions.create(**kwargs)
        return _OpenAIStreamWrapper(sdk_stream)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

VALID_PROVIDERS = ("anthropic", "openrouter", "ollama")


def build_llm_client(
    provider: str,
    *,
    model: str | None = None,
    anthropic_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    openrouter_base_url: str = OPENROUTER_BASE_URL,
    ollama_api_key: str | None = None,
    ollama_base_url: str = OLLAMA_BASE_URL,
):
    """Return an LLM client for ``provider``.

    ``model`` overrides the client's default model. Raises ``ValueError`` for an
    unknown provider or a missing key for the selected provider.
    """
    resolved_model = model or DEFAULT_MODEL
    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError("anthropic provider requires anthropic_api_key")
        return CachedAnthropic(api_key=anthropic_api_key, default_model=resolved_model)
    if provider == "openrouter":
        if not openrouter_api_key:
            raise ValueError("openrouter provider requires openrouter_api_key")
        return OpenAICompatibleClient(
            api_key=openrouter_api_key,
            base_url=openrouter_base_url,
            default_model=resolved_model,
        )
    if provider == "ollama":
        if not ollama_api_key:
            raise ValueError("ollama provider requires ollama_api_key")
        return OpenAICompatibleClient(
            api_key=ollama_api_key,
            base_url=ollama_base_url,
            default_model=resolved_model,
        )
    raise ValueError(
        f"unknown LLM provider {provider!r}; expected one of {VALID_PROVIDERS}"
    )


__all__ = [
    "OPENROUTER_BASE_URL",
    "OLLAMA_BASE_URL",
    "VALID_PROVIDERS",
    "OpenAICompatibleClient",
    "build_llm_client",
]
