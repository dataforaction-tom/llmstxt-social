"""Tests for the multi-provider LLM abstraction.

Covers the OpenAI-compatible client (OpenRouter / Ollama Cloud), the provider
factory, and the provider-neutral tool-call normalisation shared by all clients.
The Anthropic client's caching/tool behaviour is covered by test_llm.py and
test_llm_tools.py; here we only assert the normalised surface those clients
must all present.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

from llmstxt_core.llm import CachedAnthropic, CompletionResult, ToolCall
from llmstxt_core import llm_providers
from llmstxt_core.llm_providers import OpenAICompatibleClient, build_llm_client


# ---------------------------------------------------------------------------
# Helpers — fake OpenAI SDK response objects
# ---------------------------------------------------------------------------


def _openai_response(*, text=None, tool_calls=None, model="gpt-x", cached=0):
    message = SimpleNamespace(content=text, tool_calls=tool_calls)
    usage = SimpleNamespace(
        prompt_tokens=11,
        completion_tokens=22,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=usage,
        model=model,
    )


def _openai_tool_call(name, args_dict):
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=json.dumps(args_dict))
    )


def _make_client(create_return):
    """OpenAICompatibleClient with its underlying OpenAI SDK mocked."""
    fake_sdk = mock.MagicMock()
    fake_sdk.chat.completions.create.return_value = create_return
    with mock.patch.object(llm_providers, "OpenAI", return_value=fake_sdk):
        client = OpenAICompatibleClient(
            api_key="k", base_url="https://openrouter.ai/api/v1", default_model="gpt-x"
        )
    return client, fake_sdk


# ---------------------------------------------------------------------------
# Request translation
# ---------------------------------------------------------------------------


def test_complete_folds_string_system_into_messages():
    client, sdk = _make_client(_openai_response(text="hi"))
    client.complete(
        messages=[{"role": "user", "content": "hello"}], system="be terse"
    )
    sent = sdk.chat.completions.create.call_args.kwargs
    assert sent["messages"][0] == {"role": "system", "content": "be terse"}
    assert sent["messages"][1] == {"role": "user", "content": "hello"}


def test_complete_flattens_anthropic_system_blocks_and_drops_cache_control():
    client, sdk = _make_client(_openai_response(text="ok"))
    client.complete(
        messages=[{"role": "user", "content": "x"}],
        system=[
            {"type": "text", "text": "block one", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "block two"},
        ],
    )
    sent = sdk.chat.completions.create.call_args.kwargs
    assert sent["messages"][0]["role"] == "system"
    assert "block one" in sent["messages"][0]["content"]
    assert "block two" in sent["messages"][0]["content"]
    # cache_control is Anthropic-only and must not leak into the OpenAI payload.
    assert "cache_control" not in json.dumps(sent)


def test_complete_translates_tools_and_tool_choice_to_openai_shape():
    client, sdk = _make_client(_openai_response(text="ok"))
    client.complete(
        messages=[{"role": "user", "content": "x"}],
        tools=[
            {
                "name": "emit",
                "description": "emit a thing",
                "input_schema": {"type": "object", "properties": {"a": {"type": "string"}}},
            }
        ],
        tool_choice={"type": "tool", "name": "emit"},
    )
    sent = sdk.chat.completions.create.call_args.kwargs
    assert sent["tools"][0]["type"] == "function"
    assert sent["tools"][0]["function"]["name"] == "emit"
    assert sent["tools"][0]["function"]["parameters"]["properties"] == {"a": {"type": "string"}}
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "emit"}}


def test_complete_uses_call_model_over_default():
    client, sdk = _make_client(_openai_response(text="ok"))
    client.complete(messages=[{"role": "user", "content": "x"}], model="anthropic/claude")
    assert sdk.chat.completions.create.call_args.kwargs["model"] == "anthropic/claude"


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def test_complete_returns_text_and_mapped_usage():
    client, _ = _make_client(_openai_response(text="the answer", model="gpt-x", cached=5))
    result = client.complete(messages=[{"role": "user", "content": "q"}])
    assert result.text == "the answer"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 22
    assert result.usage.cache_read_tokens == 5
    assert result.usage.model == "gpt-x"


def test_complete_normalises_tool_calls():
    resp = _openai_response(
        text=None, tool_calls=[_openai_tool_call("emit", {"matches": [1, 2]})]
    )
    client, _ = _make_client(resp)
    result = client.complete(messages=[{"role": "user", "content": "q"}])
    assert result.tool_input("emit") == {"matches": [1, 2]}
    assert result.tool_input("nope") is None


def test_complete_tolerates_missing_text():
    resp = _openai_response(text=None, tool_calls=[_openai_tool_call("emit", {"x": 1})])
    client, _ = _make_client(resp)
    result = client.complete(messages=[{"role": "user", "content": "q"}])
    assert result.text == ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_build_llm_client_anthropic():
    with mock.patch("llmstxt_core.llm.Anthropic"):
        client = build_llm_client("anthropic", model="claude-sonnet-4-6", anthropic_api_key="a")
    assert isinstance(client, CachedAnthropic)
    assert client.default_model == "claude-sonnet-4-6"


def test_build_llm_client_openrouter():
    with mock.patch.object(llm_providers, "OpenAI") as fake:
        client = build_llm_client(
            "openrouter",
            model="anthropic/claude-3.5-sonnet",
            openrouter_api_key="or-key",
            openrouter_base_url="https://openrouter.ai/api/v1",
        )
    assert isinstance(client, OpenAICompatibleClient)
    assert client.default_model == "anthropic/claude-3.5-sonnet"
    # constructed with the OpenRouter key + base_url
    _, kwargs = fake.call_args
    assert kwargs["api_key"] == "or-key"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"


def test_build_llm_client_ollama():
    with mock.patch.object(llm_providers, "OpenAI") as fake:
        client = build_llm_client(
            "ollama",
            model="llama3.1",
            ollama_api_key="ol-key",
            ollama_base_url="https://ollama.com/v1",
        )
    assert isinstance(client, OpenAICompatibleClient)
    _, kwargs = fake.call_args
    assert kwargs["base_url"] == "https://ollama.com/v1"


def test_build_llm_client_rejects_unknown_provider():
    with pytest.raises(ValueError):
        build_llm_client("mistral", model="x")


# ---------------------------------------------------------------------------
# Shared normalisation — the Anthropic client must present the same surface
# ---------------------------------------------------------------------------


def test_anthropic_client_normalises_tool_calls():
    raw = SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", name="emit", input={"matches": ["a"]}),
        ],
        usage=SimpleNamespace(
            input_tokens=1, output_tokens=2, cache_creation_input_tokens=0, cache_read_input_tokens=0
        ),
        model="claude-sonnet-4-6",
    )
    with mock.patch("llmstxt_core.llm.Anthropic") as fake:
        fake.return_value.messages.create.return_value = raw
        client = CachedAnthropic(api_key="a", default_model="claude-sonnet-4-6")
        result = client.complete(messages=[{"role": "user", "content": "x"}])
    assert isinstance(result, CompletionResult)
    assert result.tool_input("emit") == {"matches": ["a"]}


def test_completion_result_tool_input_helper():
    result = CompletionResult(text="", usage=None, tool_calls=[ToolCall("emit", {"k": 1})])
    assert result.tool_input("emit") == {"k": 1}
    assert result.tool_input("missing") is None
