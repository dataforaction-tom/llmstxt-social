"""Tests for the top-level markdown_to_json / json_to_markdown converter."""

import pytest

from tests.open_org._examples import IDEA_MD, PROFILE_MD, STRATEGY_MD


# --- markdown_to_json --------------------------------------------------------

def test_markdown_to_json_profile():
    from llmstxt_core.open_org.converter import markdown_to_json
    payload = markdown_to_json(PROFILE_MD, kind="profile")
    assert payload["identity"]["name"] == "Riverside Community Trust"
    assert payload["mission"]["summary"].startswith("Supporting isolated older people")
    assert payload["mission"]["theory_of_change"].startswith("We believe")
    assert payload["culture"]["narrative"].startswith("We're a small team")
    assert payload["values"] == [
        "Everyone deserves connection",
        "Listen before you act",
        "Be honest about failure",
    ]


def test_markdown_to_json_profile_validates_against_schema():
    from llmstxt_core.open_org.converter import markdown_to_json
    from llmstxt_core.open_org.validator import validate_for_kind
    payload = markdown_to_json(PROFILE_MD, kind="profile")
    validate_for_kind(payload, kind="profile")


def test_markdown_to_json_strategy():
    from llmstxt_core.open_org.converter import markdown_to_json
    payload = markdown_to_json(STRATEGY_MD, kind="strategy")
    assert payload["summary"].startswith("Three-year plan")
    assert len(payload["not_doing"]) == 2
    assert payload["not_doing"][0]["title"] == "Opening a food bank."
    assert len(payload["tensions"]) == 1
    assert payload["tensions"][0]["title"] == "Growth vs depth."
    assert len(payload["learning"]["what_changed"]) == 2
    assert payload["learning"]["what_changed"][0]["source"] == "programme_failure"


def test_markdown_to_json_strategy_validates():
    from llmstxt_core.open_org.converter import markdown_to_json
    from llmstxt_core.open_org.validator import validate_for_kind
    payload = markdown_to_json(STRATEGY_MD, kind="strategy")
    validate_for_kind(payload, kind="strategy")


def test_markdown_to_json_idea():
    from llmstxt_core.open_org.converter import markdown_to_json
    payload = markdown_to_json(IDEA_MD, kind="idea")
    assert payload["summary"].startswith("A network")
    assert payload["detail"].startswith("Each kitchen")


def test_markdown_to_json_idea_validates():
    from llmstxt_core.open_org.converter import markdown_to_json
    from llmstxt_core.open_org.validator import validate_for_kind
    payload = markdown_to_json(IDEA_MD, kind="idea")
    validate_for_kind(payload, kind="idea")


def test_markdown_to_json_strips_comments_in_body():
    from llmstxt_core.open_org.converter import markdown_to_json
    md = PROFILE_MD.replace(
        "## Mission\n\nSupporting",
        "## Mission\n\n<!-- TODO: rewrite -->\nSupporting",
    )
    payload = markdown_to_json(md, kind="profile")
    assert "TODO" not in payload["mission"]["summary"]


def test_markdown_to_json_missing_required_fields_raises():
    from llmstxt_core.open_org.converter import markdown_to_json, ConverterError
    incomplete = "---\nschema_version: open-org/v0.1\n---\n\n## Mission\n\nWords."
    with pytest.raises(ConverterError) as excinfo:
        markdown_to_json(incomplete, kind="profile")
    err = excinfo.value
    assert err.errors, "ConverterError must carry structured errors"


def test_markdown_to_json_unknown_kind_raises():
    from llmstxt_core.open_org.converter import markdown_to_json
    with pytest.raises(ValueError, match="unknown kind"):
        markdown_to_json("---\n---\n", kind="not_a_real_kind")


# --- json_to_markdown --------------------------------------------------------

def test_json_to_markdown_profile_produces_parseable_output():
    from llmstxt_core.open_org.converter import markdown_to_json, json_to_markdown
    payload = markdown_to_json(PROFILE_MD, kind="profile")
    md = json_to_markdown(payload, kind="profile")
    # Header markers and body sections should be present.
    assert "---" in md
    assert "## Mission" in md
    assert "## Values" in md
    # Re-parsing yields the same payload.
    re_parsed = markdown_to_json(md, kind="profile")
    assert re_parsed == payload


def test_json_to_markdown_strategy_produces_parseable_output():
    from llmstxt_core.open_org.converter import markdown_to_json, json_to_markdown
    payload = markdown_to_json(STRATEGY_MD, kind="strategy")
    md = json_to_markdown(payload, kind="strategy")
    assert "## Summary" in md
    assert "## Not doing" in md
    assert "## Learning" in md
    re_parsed = markdown_to_json(md, kind="strategy")
    assert re_parsed == payload


def test_json_to_markdown_idea_produces_parseable_output():
    from llmstxt_core.open_org.converter import markdown_to_json, json_to_markdown
    payload = markdown_to_json(IDEA_MD, kind="idea")
    md = json_to_markdown(payload, kind="idea")
    assert "## Summary" in md
    assert "## The detail" in md
    re_parsed = markdown_to_json(md, kind="idea")
    assert re_parsed == payload


def test_json_to_markdown_unknown_kind_raises():
    from llmstxt_core.open_org.converter import json_to_markdown
    with pytest.raises(ValueError, match="unknown kind"):
        json_to_markdown({"x": 1}, kind="not_a_real_kind")
