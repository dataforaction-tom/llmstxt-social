"""Tests for the Open Org theme extractor.

The extractor turns CC text (objects + activities) into a list of theme keys
from the controlled vocabulary. It uses Claude tool_use for guaranteed-valid
JSON; tests mock the SDK so they're hermetic.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.theme_extractor import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    extract_themes,
)


def _stub_response(matches: list[dict]):
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.usage = MagicMock(
        input_tokens=100,
        output_tokens=20,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "emit_theme_matches"
    tool_block.input = {"matches": matches}
    response.content = [tool_block]
    return response


def _client_returning(matches: list[dict]) -> CachedAnthropic:
    client = CachedAnthropic(api_key="test")
    client._client = MagicMock()
    client._client.messages.create.return_value = _stub_response(matches)
    return client


def test_extract_themes_returns_empty_for_empty_text():
    """No model call when there's nothing to extract from."""
    client = CachedAnthropic(api_key="test")
    client._client = MagicMock()

    result = extract_themes(client=client, objects_text="", activities_text="")

    assert result.themes == []
    assert result.flagged == []
    client._client.messages.create.assert_not_called()


def test_extract_themes_filters_below_confidence_threshold():
    client = _client_returning(
        [
            {"theme": "education", "confidence": 0.92, "reason": "..."},
            {"theme": "health", "confidence": 0.55, "reason": "..."},
            {"theme": "children_and_young_people", "confidence": 0.81, "reason": "..."},
        ]
    )

    result = extract_themes(
        client=client,
        objects_text="To advance education for young people",
        activities_text="Running after-school clubs",
    )

    assert "education" in result.themes
    assert "children_and_young_people" in result.themes
    assert "health" not in result.themes
    assert any(f["theme"] == "health" for f in result.flagged)


def test_extract_themes_drops_unknown_keys():
    """The model can hallucinate keys outside the vocabulary; we silently drop them."""
    client = _client_returning(
        [
            {"theme": "education", "confidence": 0.95, "reason": "..."},
            {"theme": "made_up_theme", "confidence": 0.99, "reason": "..."},
        ]
    )

    result = extract_themes(
        client=client,
        objects_text="schools and education",
        activities_text="teaching",
    )

    assert result.themes == ["education"]


def test_extract_themes_dedupes_repeated_keys():
    client = _client_returning(
        [
            {"theme": "education", "confidence": 0.92, "reason": "..."},
            {"theme": "education", "confidence": 0.99, "reason": "..."},
        ]
    )

    result = extract_themes(
        client=client,
        objects_text="x",
        activities_text="y",
    )

    assert result.themes == ["education"]


def test_extract_themes_returns_empty_on_missing_tool_call():
    """Defensive: model occasionally returns prose. We treat that as no themes."""
    client = CachedAnthropic(api_key="test")
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I'd say education and health"
    response.content = [text_block]
    client._client = MagicMock()
    client._client.messages.create.return_value = response

    result = extract_themes(
        client=client, objects_text="x", activities_text="y"
    )

    assert result.themes == []
    assert result.flagged == []


def test_extract_themes_passes_tool_choice_to_force_call():
    client = _client_returning([])
    extract_themes(client=client, objects_text="x", activities_text="y")
    kwargs = client._client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"]["type"] == "tool"
    assert kwargs["tool_choice"]["name"] == "emit_theme_matches"
    assert kwargs["tools"][0]["name"] == "emit_theme_matches"


def test_extract_themes_returns_usage_for_billing():
    client = _client_returning(
        [{"theme": "education", "confidence": 0.92, "reason": "..."}]
    )
    result = extract_themes(client=client, objects_text="x", activities_text="y")
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 20


def test_default_threshold_matches_spec():
    """Spec section 1: 'Accept themes above 0.7 confidence'."""
    assert DEFAULT_CONFIDENCE_THRESHOLD == 0.7


def test_extract_themes_caches_vocabulary_in_system_prompt():
    """The theme vocabulary is large and stable; it must be cached."""
    client = _client_returning([])
    extract_themes(client=client, objects_text="x", activities_text="y")
    kwargs = client._client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list)
    cached_blocks = [b for b in system if b.get("cache_control")]
    assert cached_blocks, "vocabulary block must be cached"


# --- website_text augmentation (v0.2.1) ------------------------------------


def test_website_text_is_included_in_user_message_when_provided():
    """The baseline v0.1 run showed CC text alone is too sparse for orgs
    like Trussell Trust and Shelter. Website content closes the gap."""
    client = _client_returning([])
    extract_themes(
        client=client,
        objects_text="x",
        activities_text="y",
        website_text="We run food banks across the UK.",
    )
    kwargs = client._client.messages.create.call_args.kwargs
    user_content = kwargs["messages"][-1]["content"]
    assert "food banks" in user_content


def test_website_text_omitted_when_empty():
    """An empty website_text must not pollute the prompt with empty sections."""
    client = _client_returning([])
    extract_themes(
        client=client,
        objects_text="x",
        activities_text="y",
        website_text="",
    )
    kwargs = client._client.messages.create.call_args.kwargs
    user_content = kwargs["messages"][-1]["content"]
    # No empty website-text marker.
    assert "Website content" not in user_content or "(not supplied)" in user_content


def test_website_text_triggers_model_call_even_when_cc_fields_empty():
    """Sparse CC data alone wouldn't fire the call (early-return), but a
    populated website is enough signal to attempt extraction."""
    client = _client_returning(
        [{"theme": "food_access", "confidence": 0.95, "reason": "food bank work"}]
    )
    result = extract_themes(
        client=client,
        objects_text="",
        activities_text="",
        website_text="We operate a network of food banks.",
    )
    assert "food_access" in result.themes
    client._client.messages.create.assert_called_once()


def test_no_call_when_all_three_inputs_are_empty():
    client = CachedAnthropic(api_key="test")
    client._client = MagicMock()
    result = extract_themes(
        client=client, objects_text="", activities_text="", website_text=""
    )
    assert result.themes == []
    client._client.messages.create.assert_not_called()
