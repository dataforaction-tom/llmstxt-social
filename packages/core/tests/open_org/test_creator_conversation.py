"""Tests for the chat creator's conversation orchestrator.

Exercises prompt loading, system block assembly, streaming text deltas, and
tool_use extraction of the live preview markdown. The Anthropic SDK is
mocked end-to-end so the suite is offline.
"""

from __future__ import annotations

from unittest import mock

import pytest

from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.creator.conversation import (
    UPDATE_TOOL_NAME,
    load_prompt,
    start_turn,
)


# --- Prompt loading -------------------------------------------------------


def test_load_prompt_returns_strategy_text():
    text = load_prompt("strategy")
    assert "strategy" in text.lower()
    assert "update_current_markdown" in text


def test_load_prompt_returns_idea_text():
    text = load_prompt("idea")
    assert "idea" in text.lower()
    assert "update_current_markdown" in text


def test_load_prompt_rejects_unknown_kind():
    with pytest.raises(ValueError):
        load_prompt("strategey")  # typo intentional


# --- Streaming -----------------------------------------------------------


class _FakeSdkStream:
    """Mimics the Anthropic SDK stream context manager."""

    def __init__(self, *, text_deltas, final_message):
        self._text_deltas = text_deltas
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        return iter(self._text_deltas)

    def get_final_message(self):
        return self._final_message


def _final_message(*, text: str, markdown: str | None):
    text_block = mock.MagicMock()
    text_block.type = "text"
    text_block.text = text

    blocks = [text_block]
    if markdown is not None:
        tool_block = mock.MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = UPDATE_TOOL_NAME
        tool_block.input = {"markdown": markdown}
        blocks.append(tool_block)

    msg = mock.MagicMock()
    msg.content = blocks
    msg.model = "claude-sonnet-4-20250514"
    msg.usage = mock.MagicMock(
        input_tokens=100,
        output_tokens=40,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return msg


def _client_streaming(*, text_deltas, final_markdown):
    fake_stream = _FakeSdkStream(
        text_deltas=text_deltas,
        final_message=_final_message(
            text="".join(text_deltas), markdown=final_markdown
        ),
    )
    client = CachedAnthropic(api_key="test")
    client._client = mock.MagicMock()
    client._client.messages.stream.return_value = fake_stream
    return client, fake_stream


def test_start_turn_streams_text_deltas_in_order():
    client, _ = _client_streaming(
        text_deltas=["Hello", " — ", "what's the name of this strategy?"],
        final_markdown="---\nschema_version: open-org-strategy/v0.1\n---\n",
    )

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="Hi",
    ) as turn:
        chunks = list(turn.text_stream)

    assert "".join(chunks) == "Hello — what's the name of this strategy?"


def test_start_turn_exposes_final_markdown_from_tool_call():
    client, _ = _client_streaming(
        text_deltas=["ok"],
        final_markdown=(
            "---\nschema_version: open-org-idea/v0.1\nid: x\nstatus: seed\n"
            "name: X\nthemes:\n  - education\n---\n\n## Summary\n\nA seed idea.\n"
        ),
    )

    with start_turn(
        client=client,
        kind="idea",
        conversation_history=[],
        user_message="I want to start a homework club",
    ) as turn:
        for _ in turn.text_stream:
            pass
        assert turn.final_markdown() is not None
        assert "open-org-idea/v0.1" in turn.final_markdown()


def test_start_turn_returns_none_markdown_when_tool_not_called():
    """The first turn often produces no markdown yet; that's fine."""
    client, _ = _client_streaming(
        text_deltas=["What would you like to call this strategy?"],
        final_markdown=None,
    )

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="Help me write a strategy",
    ) as turn:
        for _ in turn.text_stream:
            pass
        assert turn.final_markdown() is None


def test_start_turn_passes_conversation_history():
    """Prior turns must be replayed so the model has context."""
    client, _ = _client_streaming(text_deltas=["ok"], final_markdown=None)

    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "What's the strategy called?"},
    ]
    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=history,
        user_message="Riverside 2030",
    ) as turn:
        for _ in turn.text_stream:
            pass

    kwargs = client._client.messages.stream.call_args.kwargs
    messages = kwargs["messages"]
    # History + new user message in order, no system prompts in there.
    assert messages[0] == {"role": "user", "content": "Hi"}
    assert messages[1] == {"role": "assistant", "content": "What's the strategy called?"}
    assert messages[-1] == {"role": "user", "content": "Riverside 2030"}


def test_start_turn_caches_prompt_and_vocabulary_system_blocks():
    """Stable system text is sent as cache_control=ephemeral blocks."""
    client, _ = _client_streaming(text_deltas=["x"], final_markdown=None)

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="hi",
    ) as turn:
        for _ in turn.text_stream:
            pass

    kwargs = client._client.messages.stream.call_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list)
    cached = [b for b in system if b.get("cache_control")]
    # Prompt + vocabulary both cached (2 blocks at least).
    assert len(cached) >= 2


def test_start_turn_includes_org_context_when_provided():
    """If we have profile context, fold it into system blocks (non-cached;
    it varies per org)."""
    client, _ = _client_streaming(text_deltas=["x"], final_markdown=None)

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="hi",
        org_profile_summary="Riverside Community Trust — supports older people in Norfolk.",
    ) as turn:
        for _ in turn.text_stream:
            pass

    system = client._client.messages.stream.call_args.kwargs["system"]
    joined = " ".join(b.get("text", "") for b in system if isinstance(b, dict))
    assert "Riverside Community Trust" in joined


def test_start_turn_declares_update_current_markdown_tool():
    client, _ = _client_streaming(text_deltas=["x"], final_markdown=None)

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="hi",
    ) as turn:
        for _ in turn.text_stream:
            pass

    tools = client._client.messages.stream.call_args.kwargs["tools"]
    names = [t["name"] for t in tools]
    assert UPDATE_TOOL_NAME in names


def test_usage_is_available_after_stream_completes():
    client, _ = _client_streaming(text_deltas=["x"], final_markdown=None)

    with start_turn(
        client=client,
        kind="strategy",
        conversation_history=[],
        user_message="hi",
    ) as turn:
        for _ in turn.text_stream:
            pass
        usage = turn.usage()

    assert usage.input_tokens == 100
    assert usage.output_tokens == 40
