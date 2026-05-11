"""Tests for converter foundations: frontmatter parsing and comment stripping."""

import pytest


def test_parse_frontmatter_extracts_yaml_block():
    from llmstxt_core.open_org.converter import parse_frontmatter

    md = """---
title: Hello
themes:
  - food_access
---

This is the body.
"""
    frontmatter, body = parse_frontmatter(md)
    assert frontmatter == {"title": "Hello", "themes": ["food_access"]}
    assert body.strip() == "This is the body."


def test_parse_frontmatter_no_frontmatter_returns_empty_dict():
    from llmstxt_core.open_org.converter import parse_frontmatter

    md = "Just body text, no frontmatter."
    frontmatter, body = parse_frontmatter(md)
    assert frontmatter == {}
    assert body.strip() == "Just body text, no frontmatter."


def test_parse_frontmatter_invalid_yaml_raises_converter_error():
    from llmstxt_core.open_org.converter import parse_frontmatter, ConverterError

    md = """---
title: "unclosed quote
themes:
  - food_access
---
body
"""
    with pytest.raises(ConverterError) as excinfo:
        parse_frontmatter(md)
    assert "frontmatter" in str(excinfo.value).lower() or "yaml" in str(excinfo.value).lower()


def test_strip_comments_removes_inline_html_comments():
    from llmstxt_core.open_org.converter import strip_comments

    body = "Visible <!-- hidden --> visible too."
    assert strip_comments(body) == "Visible  visible too."


def test_strip_comments_removes_multiline_comments():
    from llmstxt_core.open_org.converter import strip_comments

    body = """Line 1
<!-- This is
a multi-line
comment -->
Line 2"""
    out = strip_comments(body)
    assert "multi-line" not in out
    assert "Line 1" in out
    assert "Line 2" in out


def test_strip_comments_preserves_code_blocks():
    """Comments inside fenced code blocks should not be stripped — they may be intentional content."""
    from llmstxt_core.open_org.converter import strip_comments

    body = """Some prose.

```html
<!-- this comment is example code -->
```

More prose."""
    out = strip_comments(body)
    assert "<!-- this comment is example code -->" in out


def test_strip_comments_handles_no_comments():
    from llmstxt_core.open_org.converter import strip_comments
    body = "Plain markdown with no HTML comments at all."
    assert strip_comments(body) == body


def test_converter_error_carries_structured_errors():
    """ConverterError exposes a list of {path, message} dicts like ValidationError does."""
    from llmstxt_core.open_org.converter import ConverterError

    err = ConverterError([{"path": "mission.themes", "message": "is required"}])
    assert err.errors == [{"path": "mission.themes", "message": "is required"}]
    assert "mission.themes" in str(err) or "is required" in str(err)
