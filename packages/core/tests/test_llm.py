"""Tests for the CachedAnthropic wrapper.

Mocks the underlying ``anthropic.Anthropic`` client so these run without
network access or an API key.
"""

from unittest import mock

import pytest


# --- helpers -----------------------------------------------------------------

def _mock_anthropic_response(
    text: str = "ok",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    model: str = "claude-sonnet-4-20250514",
):
    """Build a Mock Anthropic Message that behaves like the SDK return type."""
    response = mock.MagicMock()
    block = mock.MagicMock()
    block.type = "text"
    block.text = text
    response.content = [block]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.usage.cache_creation_input_tokens = cache_creation_tokens
    response.usage.cache_read_input_tokens = cache_read_tokens
    response.model = model
    return response


# --- system_block helper -----------------------------------------------------

def test_system_block_without_cache():
    from llmstxt_core.llm import system_block
    assert system_block("You are helpful.") == {
        "type": "text",
        "text": "You are helpful.",
    }


def test_system_block_with_cache_adds_ephemeral_control():
    from llmstxt_core.llm import system_block
    assert system_block("Long context", cache=True) == {
        "type": "text",
        "text": "Long context",
        "cache_control": {"type": "ephemeral"},
    }


# --- complete() --------------------------------------------------------------

@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_returns_text_and_usage(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response(
        text="hello world", input_tokens=120, output_tokens=80
    )

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.text == "hello world"
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 80
    assert result.usage.cache_creation_tokens == 0
    assert result.usage.cache_read_tokens == 0
    assert result.usage.model == "claude-sonnet-4-20250514"


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_uses_default_model(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic, DEFAULT_MODEL
    client = CachedAnthropic(api_key="x")
    client.complete(messages=[{"role": "user", "content": "hi"}])

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["model"] == DEFAULT_MODEL


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_uses_overridden_model(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    client.complete(
        messages=[{"role": "user", "content": "hi"}],
        model="claude-haiku-4-5",
    )

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_passes_string_system_prompt(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    client.complete(
        system="You are concise.",
        messages=[{"role": "user", "content": "hi"}],
    )

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are concise."


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_passes_structured_system_blocks_with_cache_control(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic, system_block
    client = CachedAnthropic(api_key="x")
    client.complete(
        system=[
            system_block("You are helpful."),
            system_block("<theme vocabulary>", cache=True),
        ],
        messages=[{"role": "user", "content": "hi"}],
    )

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["system"] == [
        {"type": "text", "text": "You are helpful."},
        {"type": "text", "text": "<theme vocabulary>", "cache_control": {"type": "ephemeral"}},
    ]


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_records_cache_token_usage(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response(
        cache_creation_tokens=1000, cache_read_tokens=4000
    )

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.usage.cache_creation_tokens == 1000
    assert result.usage.cache_read_tokens == 4000


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_passes_max_tokens_and_temperature(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    client.complete(
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=8192,
        temperature=0.2,
    )

    call_kwargs = instance.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 8192
    assert call_kwargs["temperature"] == 0.2


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_concatenates_multiple_text_blocks_in_response(mock_class):
    """Some Anthropic responses contain multiple text blocks (e.g. with thinking)."""
    instance = mock_class.return_value
    response = mock.MagicMock()
    block1 = mock.MagicMock(); block1.type = "text"; block1.text = "Part one. "
    block2 = mock.MagicMock(); block2.type = "text"; block2.text = "Part two."
    response.content = [block1, block2]
    response.usage.input_tokens = 1
    response.usage.output_tokens = 1
    response.usage.cache_creation_input_tokens = 0
    response.usage.cache_read_input_tokens = 0
    response.model = "x"
    instance.messages.create.return_value = response

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.text == "Part one. Part two."


@mock.patch("llmstxt_core.llm.Anthropic")
def test_complete_skips_non_text_blocks(mock_class):
    """Tool use / image blocks shouldn't end up in the .text attribute."""
    instance = mock_class.return_value
    response = mock.MagicMock()
    text_block = mock.MagicMock(); text_block.type = "text"; text_block.text = "answer"
    tool_block = mock.MagicMock(); tool_block.type = "tool_use"
    response.content = [text_block, tool_block]
    response.usage.input_tokens = 1
    response.usage.output_tokens = 1
    response.usage.cache_creation_input_tokens = 0
    response.usage.cache_read_input_tokens = 0
    response.model = "x"
    instance.messages.create.return_value = response

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")
    result = client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.text == "answer"


@mock.patch("llmstxt_core.llm.Anthropic")
def test_client_constructed_with_api_key(mock_class):
    instance = mock_class.return_value
    instance.messages.create.return_value = _mock_anthropic_response()

    from llmstxt_core.llm import CachedAnthropic
    CachedAnthropic(api_key="sk-test-abc")
    mock_class.assert_called_once_with(api_key="sk-test-abc")


# --- stream() ---------------------------------------------------------------

@mock.patch("llmstxt_core.llm.Anthropic")
def test_stream_yields_text_deltas_then_returns_usage(mock_class):
    instance = mock_class.return_value

    # The SDK's stream() returns a context manager whose iter yields events.
    stream_cm = mock.MagicMock()
    stream_cm.__enter__.return_value = stream_cm
    stream_cm.__exit__.return_value = False
    stream_cm.text_stream = iter(["Hello", ", ", "world!"])
    final_message = _mock_anthropic_response(
        text="Hello, world!", input_tokens=10, output_tokens=3
    )
    stream_cm.get_final_message.return_value = final_message
    instance.messages.stream.return_value = stream_cm

    from llmstxt_core.llm import CachedAnthropic
    client = CachedAnthropic(api_key="x")

    deltas: list[str] = []
    with client.stream(messages=[{"role": "user", "content": "say hi"}]) as stream:
        for delta in stream.text_stream:
            deltas.append(delta)
        final_usage = stream.usage()

    assert deltas == ["Hello", ", ", "world!"]
    assert final_usage.input_tokens == 10
    assert final_usage.output_tokens == 3


@mock.patch("llmstxt_core.llm.Anthropic")
def test_stream_passes_system_blocks_and_messages(mock_class):
    instance = mock_class.return_value
    stream_cm = mock.MagicMock()
    stream_cm.__enter__.return_value = stream_cm
    stream_cm.__exit__.return_value = False
    stream_cm.text_stream = iter([])
    stream_cm.get_final_message.return_value = _mock_anthropic_response()
    instance.messages.stream.return_value = stream_cm

    from llmstxt_core.llm import CachedAnthropic, system_block
    client = CachedAnthropic(api_key="x")
    with client.stream(
        system=[system_block("rules", cache=True)],
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=512,
    ) as stream:
        list(stream.text_stream)

    call_kwargs = instance.messages.stream.call_args.kwargs
    assert call_kwargs["system"] == [
        {"type": "text", "text": "rules", "cache_control": {"type": "ephemeral"}}
    ]
    assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert call_kwargs["max_tokens"] == 512


# --- usage helpers ----------------------------------------------------------

def test_usage_total_input_tokens_includes_cache_reads():
    """Cache reads still count as input tokens for billing — usage.billable_input
    surfaces this for cost calculation."""
    from llmstxt_core.llm import Usage
    u = Usage(
        input_tokens=100,
        output_tokens=50,
        cache_creation_tokens=200,
        cache_read_tokens=400,
        model="x",
    )
    # The plain input_tokens from Anthropic is JUST the uncached portion.
    # Cache reads + cache writes + input together form the full input cost basis.
    assert u.billable_input_tokens() == 100 + 200 + 400
