"""Settings.build_llm_client wires env config to the provider factory.

Verifies the provider switch is honoured end-to-end: changing LLM_PROVIDER /
LLM_MODEL (here via monkeypatch on the loaded settings) selects the right client
without touching code.
"""

from __future__ import annotations

from unittest import mock

import pytest

from llmstxt_api.config import settings
from llmstxt_core.llm import CachedAnthropic
from llmstxt_core import llm_providers
from llmstxt_core.llm_providers import OpenAICompatibleClient


def test_build_llm_client_defaults_to_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_model", "claude-sonnet-4-6")
    with mock.patch("llmstxt_core.llm.Anthropic"):
        client = settings.build_llm_client()
    assert isinstance(client, CachedAnthropic)
    assert client.default_model == "claude-sonnet-4-6"


def test_build_llm_client_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "llm_model", "anthropic/claude-3.5-sonnet")
    monkeypatch.setattr(settings, "openrouter_api_key", "or-key")
    with mock.patch.object(llm_providers, "OpenAI") as fake:
        client = settings.build_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
    assert client.default_model == "anthropic/claude-3.5-sonnet"
    assert fake.call_args.kwargs["api_key"] == "or-key"


def test_build_llm_client_ollama(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "llama3.1")
    monkeypatch.setattr(settings, "ollama_api_key", "ol-key")
    with mock.patch.object(llm_providers, "OpenAI") as fake:
        client = settings.build_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
    assert "ollama.com" in fake.call_args.kwargs["base_url"]


def test_build_llm_client_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    with pytest.raises(ValueError):
        settings.build_llm_client()
