"""Tests for the mission summary rewriter.

Spec section 1: take CC ``activities`` text and rewrite into plain language,
capped at 500 characters. Mocks the SDK so it stays offline.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.mission_rewriter import (
    MISSION_SUMMARY_MAX_CHARS,
    rewrite_mission_summary,
)


def _client_returning_text(text: str) -> CachedAnthropic:
    client = CachedAnthropic(api_key="test")
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.usage = MagicMock(
        input_tokens=50,
        output_tokens=20,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response.content = [text_block]
    client._client = MagicMock()
    client._client.messages.create.return_value = response
    return client


def test_rewrites_activities_text():
    client = _client_returning_text("We help young people get into work.")
    result = rewrite_mission_summary(
        client=client,
        activities_text="The provision of training and skills development for young persons aged 16-25.",
    )
    assert result.summary == "We help young people get into work."


def test_returns_empty_for_empty_input_without_calling_model():
    client = CachedAnthropic(api_key="test")
    client._client = MagicMock()

    result = rewrite_mission_summary(client=client, activities_text="")

    assert result.summary == ""
    client._client.messages.create.assert_not_called()


def test_returns_empty_for_whitespace_only_input():
    client = CachedAnthropic(api_key="test")
    client._client = MagicMock()
    result = rewrite_mission_summary(client=client, activities_text="   \n  ")
    assert result.summary == ""
    client._client.messages.create.assert_not_called()


def test_caps_summary_at_max_chars():
    """Long model output is hard-truncated to the schema limit (500 chars).

    The schema enforces this on validate, so a smarter approach would be to
    re-prompt; for MVP we hard-truncate and rely on the user editing.
    """
    long_text = "A" * 800
    client = _client_returning_text(long_text)
    result = rewrite_mission_summary(client=client, activities_text="x")
    assert len(result.summary) <= MISSION_SUMMARY_MAX_CHARS


def test_strips_surrounding_whitespace_and_quotes():
    """Models sometimes wrap output in quotes or add a trailing newline."""
    client = _client_returning_text('  "We help young people."  \n')
    result = rewrite_mission_summary(client=client, activities_text="x")
    assert result.summary == "We help young people."


def test_returns_usage_for_billing():
    client = _client_returning_text("hi")
    result = rewrite_mission_summary(client=client, activities_text="x")
    assert result.usage.input_tokens == 50
    assert result.usage.output_tokens == 20


def test_uses_zero_temperature_for_determinism():
    """Mission summaries should be reproducible across re-generations."""
    client = _client_returning_text("hi")
    rewrite_mission_summary(client=client, activities_text="x")
    kwargs = client._client.messages.create.call_args.kwargs
    assert kwargs["temperature"] == 0
