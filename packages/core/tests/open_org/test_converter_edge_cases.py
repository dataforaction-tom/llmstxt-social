"""Edge-case tests for the Open Org converter — bugs found in audit.

Each test was written red first, then the converter was fixed to make it green.
Covers: fenced code blocks with ## headings, strategy priorities parsing,
plain (non-bold) items in not_doing/tensions, empty body, special characters,
nested frontmatter arrays, long values, numeric-looking strings on input.
"""

import pytest

from llmstxt_core.open_org.converter import (
    json_to_markdown,
    markdown_to_json,
    parse_bold_items,
    strip_comments,
)
from tests.open_org._examples import IDEA_MD, PROFILE_MD, STRATEGY_MD


# --- fenced code blocks containing ## headings -------------------------------

def test_code_block_heading_after_real_section_overwrites():
    """A ## heading inside a fenced code block that appears AFTER the real
    section of the same name must NOT overwrite the real section's content.
    This is the critical case — the code-block content leaks into the JSON."""
    md = """---
schema_version: open-org/v0.1
identity:
  name: "Trust"
  registration:
    other: "reg-1"
mission:
  themes:
    - health
---

## Values

- real value

## Culture

We have a culture.

```markdown
## Values
- fake value from code block
```
"""
    payload = markdown_to_json(md, kind="profile")
    assert payload["values"] == ["real value"]
    assert "fake" not in payload.get("culture", {}).get("narrative", "")


def test_code_block_with_hash_headings_not_parsed_as_sections():
    """A ## heading inside a fenced code block must not become a body section."""
    md = PROFILE_MD.replace(
        "## Culture\n\nWe're a small team that moves fast and learns publicly.\n",
        '## Culture\n\nWe\'re a small team that moves fast and learns publicly.\n\n'
        '```markdown\n'
        '## Example heading inside code block\n'
        'This should not be a section.\n'
        '```\n',
    )
    payload = markdown_to_json(md, kind="profile")
    # The code block content must not appear as a separate top-level key.
    assert "Example heading inside code block" not in payload
    # Culture narrative should still be correct.
    assert payload["culture"]["narrative"].startswith("We're a small team")


def test_code_block_with_hash_headings_round_trip():
    """Round-trip must preserve code-block ## headings without treating them as sections."""
    md = STRATEGY_MD.replace(
        "## Learning\n",
        '```python\n'
        '## not a section heading\n'
        'x = 1\n'
        '```\n\n'
        '## Learning\n',
    )
    json_a = markdown_to_json(md, kind="strategy")
    md_b = json_to_markdown(json_a, kind="strategy")
    json_b = markdown_to_json(md_b, kind="strategy")
    assert json_a == json_b


# --- strategy priorities parsing from body ------------------------------------

def test_strategy_priorities_parsed_from_body():
    """## Priority 1: Title headings must map to priorities[0], priorities[1], etc."""
    md = """---
schema_version: open-org-strategy/v0.1
id: "strategy-2025"
status: draft
themes:
  - food_access
---

## Summary

A strategy with priorities.

## Priority 1: Build the network

Three kitchens in year one.

## Priority 2: Sustain volunteer base

Monthly check-ins and peer support.
"""
    payload = markdown_to_json(md, kind="strategy")
    assert "priorities" in payload
    assert len(payload["priorities"]) == 2
    assert payload["priorities"][0]["title"] == "Build the network"
    assert payload["priorities"][0]["narrative"].startswith("Three kitchens")
    assert payload["priorities"][1]["title"] == "Sustain volunteer base"


def test_strategy_priorities_round_trip():
    """Priorities must survive md→json→md→json round-trip."""
    md = """---
schema_version: open-org-strategy/v0.1
id: "strategy-2025"
status: draft
themes:
  - food_access
---

## Priority 1: First thing

Do the first thing.

## Priority 2: Second thing

Do the second thing.
"""
    json_a = markdown_to_json(md, kind="strategy")
    md_b = json_to_markdown(json_a, kind="strategy")
    json_b = markdown_to_json(md_b, kind="strategy")
    assert json_a == json_b
    assert len(json_b["priorities"]) == 2


# --- plain (non-bold) items in not_doing / tensions --------------------------

def test_parse_bold_items_handles_plain_items():
    """Items without a **bold** prefix should still be parsed, not silently dropped."""
    body = (
        "- **Opening a food bank.** Transactional food provision can undermine dignity.\n"
        "- Expanding to Norwich because we have capacity there.\n"
    )
    items = parse_bold_items(body)
    assert len(items) == 2
    assert items[1]["title"] == "Expanding to Norwich because we have capacity there."
    assert items[1]["rationale"] == ""


def test_strategy_not_doing_plain_items_round_trip():
    """A not_doing section with plain items must round-trip without data loss."""
    md = """---
schema_version: open-org-strategy/v0.1
id: "strategy-2025"
status: draft
themes:
  - food_access
---

## Not doing

- **Opening a food bank.** Transactional food provision can undermine dignity.
- Expanding to Norwich because we have capacity there.
"""
    payload = markdown_to_json(md, kind="strategy")
    assert len(payload["not_doing"]) == 2
    assert payload["not_doing"][1]["title"] == "Expanding to Norwich because we have capacity there."


# --- empty markdown body (frontmatter only) ----------------------------------

def test_empty_body_frontmatter_only_strategy():
    """A strategy with only frontmatter (no ## sections) should still convert."""
    md = """---
schema_version: open-org-strategy/v0.1
id: "strategy-2025"
status: draft
themes:
  - food_access
summary: "A strategy with no body sections."
---
"""
    payload = markdown_to_json(md, kind="strategy")
    assert payload["summary"] == "A strategy with no body sections."
    assert payload["id"] == "strategy-2025"


def test_empty_body_round_trip_idea():
    """An idea with only frontmatter should round-trip."""
    payload = {
        "schema_version": "open-org-idea/v0.1",
        "id": "idea-1",
        "status": "seed",
        "themes": ["food_access"],
        "summary": "Just a summary in frontmatter.",
    }
    md = json_to_markdown(payload, kind="idea")
    back = markdown_to_json(md, kind="idea")
    assert back == payload


# --- special characters in org names -----------------------------------------

def test_special_characters_in_org_name_round_trip():
    """Ampersands, em-dashes, and quotes in org names must survive round-trip."""
    payload = {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": "Care & Support — \"The People's Trust\"",
            "registration": {"other": "reg-123"},
        },
        "mission": {"themes": ["health"]},
    }
    md = json_to_markdown(payload, kind="profile")
    back = markdown_to_json(md, kind="profile")
    assert back["identity"]["name"] == "Care & Support — \"The People's Trust\""


def test_special_characters_in_summary_round_trip():
    payload = {
        "schema_version": "open-org-idea/v0.1",
        "id": "idea-x",
        "status": "seed",
        "themes": ["health"],
        "summary": "We help people & pets — it's a \"win-win\".",
    }
    md = json_to_markdown(payload, kind="idea")
    back = markdown_to_json(md, kind="idea")
    assert back["summary"] == "We help people & pets — it's a \"win-win\"."


# --- nested arrays in frontmatter (governance.policies) ----------------------

def test_nested_array_frontmatter_round_trip():
    """governance.policies (array of {name, last_reviewed}) must round-trip."""
    payload = {
        "schema_version": "open-org/v0.1",
        "identity": {
            "name": "Trust",
            "registration": {"other": "reg-1"},
        },
        "mission": {"themes": ["health"]},
        "governance": {
            "board_size": 7,
            "policies": [
                {"name": "Safeguarding", "last_reviewed": "2024-01-15"},
                {"name": "Data protection", "last_reviewed": "2023-11-01"},
            ],
        },
    }
    md = json_to_markdown(payload, kind="profile")
    back = markdown_to_json(md, kind="profile")
    assert back["governance"]["policies"] == payload["governance"]["policies"]


# --- very long frontmatter values --------------------------------------------

def test_very_long_frontmatter_value_round_trip():
    """A very long summary string must survive round-trip intact."""
    long_text = "A" * 5000
    payload = {
        "schema_version": "open-org-idea/v0.1",
        "id": "idea-long",
        "status": "seed",
        "themes": ["health"],
        "summary": long_text,
    }
    md = json_to_markdown(payload, kind="idea")
    back = markdown_to_json(md, kind="idea")
    assert back["summary"] == long_text


# --- numeric-looking strings on input (unquoted in YAML) ---------------------

def test_unquoted_numeric_string_in_frontmatter_coerced_to_string():
    """If a user writes charity_commission_ew: 1234567 (unquoted), it should
    still validate — the converter should coerce numeric ints back to strings
    for fields the schema requires as strings."""
    md = """---
schema_version: open-org/v0.1
identity:
  name: "Trust"
  registration:
    charity_commission_ew: 1234567
mission:
  themes:
    - health
---
"""
    payload = markdown_to_json(md, kind="profile")
    assert payload["identity"]["registration"]["charity_commission_ew"] == "1234567"
    assert isinstance(payload["identity"]["registration"]["charity_commission_ew"], str)