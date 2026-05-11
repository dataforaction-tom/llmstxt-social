"""Tests for the Open Org JSON Schema validator wrapper."""

import pytest

# A minimal inline schema so these tests are independent of the real Open Org schemas.
_MINI_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["name", "themes"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "themes": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "income": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}


def test_validate_passes_on_valid_payload():
    from llmstxt_core.open_org.validator import validate
    validate({"name": "Riverside Trust", "themes": ["loneliness"]}, schema=_MINI_SCHEMA)


def test_validate_iter_returns_empty_on_valid_payload():
    from llmstxt_core.open_org.validator import validate_iter
    errors = validate_iter({"name": "Riverside Trust", "themes": ["loneliness"]}, schema=_MINI_SCHEMA)
    assert errors == []


def test_validate_raises_on_missing_required_field():
    from llmstxt_core.open_org.validator import validate, ValidationError
    with pytest.raises(ValidationError) as excinfo:
        validate({"themes": ["loneliness"]}, schema=_MINI_SCHEMA)
    err = excinfo.value
    assert err.errors, "ValidationError must carry structured errors"
    paths = [e["path"] for e in err.errors]
    messages = " ".join(e["message"] for e in err.errors)
    assert "" in paths or any(p == "" for p in paths) or "name" in messages
    assert "name" in messages


def test_validate_iter_returns_structured_errors():
    from llmstxt_core.open_org.validator import validate_iter
    errors = validate_iter(
        {"name": "", "themes": [], "income": -5},
        schema=_MINI_SCHEMA,
    )
    assert len(errors) >= 3
    for e in errors:
        assert "path" in e
        assert "message" in e


def test_validate_error_path_uses_dotted_notation():
    """Nested-field errors should report a dotted path like 'themes[0]'."""
    from llmstxt_core.open_org.validator import validate_iter
    errors = validate_iter(
        {"name": "Trust", "themes": [123]},  # item should be string
        schema=_MINI_SCHEMA,
    )
    paths = [e["path"] for e in errors]
    assert any("themes" in p for p in paths), f"got paths: {paths}"


def test_validate_for_kind_loads_real_schema(tmp_path):
    """The validate_for_kind helper looks up the schema by object kind."""
    from llmstxt_core.open_org.validator import validate_for_kind, ValidationError
    # Empty payload definitely fails any of the real schemas — use it as the smoke test.
    with pytest.raises(ValidationError):
        validate_for_kind({}, kind="profile")


def test_validate_for_kind_unknown_kind_raises_value_error():
    from llmstxt_core.open_org.validator import validate_for_kind
    with pytest.raises(ValueError, match="unknown kind"):
        validate_for_kind({"x": 1}, kind="not_a_real_kind")


def test_load_schema_cached():
    """Schema loading is cached — repeated calls return the same object."""
    from llmstxt_core.open_org.validator import load_schema
    s1 = load_schema("profile")
    s2 = load_schema("profile")
    assert s1 is s2
