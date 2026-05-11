"""Tests for tool_use support added to ``CachedAnthropic``.

The Open Org theme extractor needs guaranteed-valid JSON from the model.
Anthropic's tool_use API gives that without prose-parsing — we declare a tool
schema, force the model to call it, and read ``input`` directly. These tests
exercise the additive support and the helper that pulls the tool input out of
an SDK response.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llmstxt_core.llm import (
    CachedAnthropic,
    extract_tool_input,
)


def _make_response(*, content_blocks: list, model: str = "claude-sonnet-4-20250514"):
    response = MagicMock()
    response.model = model
    response.content = content_blocks
    response.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return response


def _tool_use_block(name: str, input_payload: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_payload
    block.text = ""  # SDK omits .text on tool_use blocks; defensive default
    return block


def _text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def test_complete_passes_tools_and_tool_choice_to_sdk():
    """When tools/tool_choice are provided, both must be forwarded to the SDK."""
    client = CachedAnthropic(api_key="test")
    sdk_response = _make_response(
        content_blocks=[_tool_use_block("emit_themes", {"matches": []})]
    )
    client._client = MagicMock()
    client._client.messages.create.return_value = sdk_response

    tool_spec = {
        "name": "emit_themes",
        "description": "Emit theme matches",
        "input_schema": {
            "type": "object",
            "properties": {"matches": {"type": "array"}},
            "required": ["matches"],
        },
    }

    result = client.complete(
        messages=[{"role": "user", "content": "hi"}],
        tools=[tool_spec],
        tool_choice={"type": "tool", "name": "emit_themes"},
    )

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["tools"] == [tool_spec]
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "emit_themes"}
    assert result.raw is sdk_response


def test_complete_omits_tools_when_not_provided():
    """The default call path must stay unchanged for callers that don't use tools."""
    client = CachedAnthropic(api_key="test")
    sdk_response = _make_response(content_blocks=[_text_block("hello")])
    client._client = MagicMock()
    client._client.messages.create.return_value = sdk_response

    client.complete(messages=[{"role": "user", "content": "hi"}])

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


def test_extract_tool_input_returns_matching_tool_block():
    response = _make_response(
        content_blocks=[
            _text_block("ignore me"),
            _tool_use_block("emit_themes", {"matches": [{"theme": "education"}]}),
        ]
    )
    payload = extract_tool_input(response, "emit_themes")
    assert payload == {"matches": [{"theme": "education"}]}


def test_extract_tool_input_returns_none_when_tool_not_called():
    response = _make_response(content_blocks=[_text_block("just text")])
    assert extract_tool_input(response, "emit_themes") is None


def test_extract_tool_input_ignores_non_matching_tool_names():
    response = _make_response(
        content_blocks=[_tool_use_block("other_tool", {"x": 1})],
    )
    assert extract_tool_input(response, "emit_themes") is None
