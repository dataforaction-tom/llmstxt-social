"""Tests for section-level parsers and renderers in the converter."""


# --- text --------------------------------------------------------------------

def test_parse_text_strips_whitespace():
    from llmstxt_core.open_org.converter import parse_text
    assert parse_text("  hello world  \n") == "hello world"


def test_parse_text_preserves_internal_newlines():
    from llmstxt_core.open_org.converter import parse_text
    assert parse_text("para 1\n\npara 2") == "para 1\n\npara 2"


def test_render_text_passes_through():
    from llmstxt_core.open_org.converter import render_text
    assert render_text("Just some prose.") == "Just some prose."


# --- bullet list -------------------------------------------------------------

def test_parse_bullet_list_simple():
    from llmstxt_core.open_org.converter import parse_bullet_list
    body = "- Everyone deserves connection\n- Listen before you act\n- Be honest"
    assert parse_bullet_list(body) == [
        "Everyone deserves connection",
        "Listen before you act",
        "Be honest",
    ]


def test_parse_bullet_list_ignores_blank_lines():
    from llmstxt_core.open_org.converter import parse_bullet_list
    body = "\n- One\n\n- Two\n\n"
    assert parse_bullet_list(body) == ["One", "Two"]


def test_render_bullet_list_round_trip():
    from llmstxt_core.open_org.converter import parse_bullet_list, render_bullet_list
    items = ["Alpha", "Beta", "Gamma"]
    rendered = render_bullet_list(items)
    assert parse_bullet_list(rendered) == items


# --- bold items (used for not-doing, tensions) ------------------------------

def test_parse_bold_items_single_item():
    from llmstxt_core.open_org.converter import parse_bold_items
    body = "- **Opening a food bank.** We've seen how transactional food provision undermines dignity."
    items = parse_bold_items(body)
    assert items == [
        {
            "title": "Opening a food bank.",
            "rationale": "We've seen how transactional food provision undermines dignity.",
        }
    ]


def test_parse_bold_items_multiple_items():
    from llmstxt_core.open_org.converter import parse_bold_items
    body = (
        "- **Opening a food bank.** We've seen how transactional food provision undermines dignity.\n"
        "- **Expanding to Norwich.** Depth in one place matters more than breadth across two."
    )
    items = parse_bold_items(body)
    assert len(items) == 2
    assert items[0]["title"] == "Opening a food bank."
    assert items[1]["title"] == "Expanding to Norwich."


def test_parse_bold_items_handles_multiline_bold_title():
    """Bold titles can wrap across multiple lines in the source markdown."""
    from llmstxt_core.open_org.converter import parse_bold_items
    body = (
        "- **The befriending programme taught us about volunteer\n"
        "  retention.** We lost 40% of volunteers in year one."
    )
    items = parse_bold_items(body)
    assert len(items) == 1
    # The title joins across lines (whitespace collapsed)
    assert "befriending programme" in items[0]["title"]
    assert "retention." in items[0]["title"]
    assert "lost 40%" in items[0]["rationale"]


def test_render_bold_items_round_trip():
    from llmstxt_core.open_org.converter import parse_bold_items, render_bold_items
    items = [
        {"title": "Title one.", "rationale": "Reason one."},
        {"title": "Title two.", "rationale": "Reason two."},
    ]
    rendered = render_bold_items(items, body_field="rationale")
    parsed = parse_bold_items(rendered)
    assert parsed == items


def test_parse_bold_items_into_narrative_field():
    """Tensions use 'narrative' rather than 'rationale' as the body field — same shape, different key."""
    from llmstxt_core.open_org.converter import parse_bold_items
    body = "- **Growth vs depth.** Three kitchens is ambitious for an organisation our size."
    items = parse_bold_items(body, body_field="narrative")
    assert items == [
        {
            "title": "Growth vs depth.",
            "narrative": "Three kitchens is ambitious for an organisation our size.",
        }
    ]


# --- bold items with source tag (learning) ----------------------------------

def test_parse_bold_items_with_source_extracts_tag():
    from llmstxt_core.open_org.converter import parse_bold_items_with_source
    body = (
        "- **Volunteer retention.** Monthly check-ins lifted retention from 40% to 80%.\n"
        "  *Source: programme_failure*"
    )
    items = parse_bold_items_with_source(body)
    assert len(items) == 1
    assert items[0]["lesson"].startswith("Monthly check-ins")
    assert items[0]["source"] == "programme_failure"


def test_parse_bold_items_with_source_no_tag_omits_source_key():
    from llmstxt_core.open_org.converter import parse_bold_items_with_source
    body = "- **Some lesson.** Description without a source tag."
    items = parse_bold_items_with_source(body)
    assert items == [{"lesson": "Description without a source tag."}]


def test_render_bold_items_with_source_round_trip():
    from llmstxt_core.open_org.converter import (
        parse_bold_items_with_source,
        render_bold_items_with_source,
    )
    items = [
        {"lesson": "Lesson one.", "source": "evaluation_2024"},
        {"lesson": "Lesson two without source."},
    ]
    rendered = render_bold_items_with_source(items)
    parsed = parse_bold_items_with_source(rendered)
    assert parsed == items
