"""Tests for the Open Org theme vocabulary."""

import json
import re
from pathlib import Path

import pytest

THEMES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "llmstxt_core" / "open_org" / "data" / "themes.json"
)
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*[a-z0-9]$")


@pytest.fixture(scope="module")
def themes():
    with THEMES_PATH.open() as f:
        return json.load(f)


def test_themes_file_exists():
    assert THEMES_PATH.exists(), f"themes.json missing at {THEMES_PATH}"


def test_themes_count_is_thirty(themes):
    assert len(themes) == 30, f"expected 30 themes, got {len(themes)}"


def test_theme_keys_are_snake_case(themes):
    for theme in themes:
        key = theme["key"]
        assert SNAKE_CASE.match(key), f"not snake_case: {key!r}"


def test_theme_keys_are_unique(themes):
    keys = [t["key"] for t in themes]
    assert len(keys) == len(set(keys)), "duplicate theme keys"


def test_each_theme_has_label_and_description(themes):
    for theme in themes:
        assert theme.get("label"), f"missing label: {theme['key']}"
        assert theme.get("description"), f"missing description: {theme['key']}"


def test_uk_policy_specific_themes_present(themes):
    """Spec calls these out as UK adds: must be in the vocab."""
    keys = {t["key"] for t in themes}
    for required in ("loneliness", "social_prescribing", "food_access", "lived_experience"):
        assert required in keys, f"missing UK-policy theme: {required}"


def test_load_themes_helper():
    from llmstxt_core.open_org.themes import load_themes, theme_keys
    themes_list = load_themes()
    assert len(themes_list) == 30
    keys = theme_keys()
    assert isinstance(keys, frozenset)
    assert "loneliness" in keys
    assert "not_a_real_theme" not in keys


def test_is_valid_theme_helper():
    from llmstxt_core.open_org.themes import is_valid_theme
    assert is_valid_theme("loneliness") is True
    assert is_valid_theme("not_a_real_theme") is False


def test_health_description_excludes_mental_health(themes):
    """v0.2.4: Mind got `health, disability` in the v0.1 baseline because
    the descriptions overlapped. The `health` description now explicitly
    points at physical health and routes mental health to mental_health."""
    health = next(t for t in themes if t["key"] == "health")
    desc = health["description"].lower()
    assert "physical" in desc, "`health` should be explicit about being physical"
    assert "mental_health" in desc or "excludes mental" in desc, (
        "`health` should route mental-health language to mental_health"
    )


def test_mental_health_description_is_unambiguous(themes):
    """The mental_health description must spell out anxiety/depression-style
    territory and explicitly distinguish from `health`."""
    mh = next(t for t in themes if t["key"] == "mental_health")
    desc = mh["description"].lower()
    assert "anxiety" in desc or "depression" in desc
    # The description must explicitly tell the model to prefer mental_health
    # over `health` for psychological wellbeing.
    assert "not health" in desc or "not the health key" in desc or "use this key" in desc


def test_schemas_theme_enum_matches_vocabulary(themes):
    """The theme enum baked into each schema must match themes.json exactly,
    or the schema will silently accept retired themes / reject new ones."""
    from llmstxt_core.open_org.validator import load_schema

    vocab_keys = {t["key"] for t in themes}
    for kind, dotted_path in [
        ("profile", ["properties", "mission", "properties", "themes", "items", "enum"]),
        ("strategy", ["properties", "themes", "items", "enum"]),
        ("idea", ["properties", "themes", "items", "enum"]),
    ]:
        node = load_schema(kind)
        for part in dotted_path:
            node = node[part]
        assert set(node) == vocab_keys, (
            f"{kind} schema theme enum out of sync with themes.json: "
            f"missing={vocab_keys - set(node)}, extra={set(node) - vocab_keys}"
        )
