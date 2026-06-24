"""YAML scalar-typing in the frontmatter renderer.

Numeric-looking string fields (phone, charity/registration number, area codes)
must be emitted *quoted*. pyyaml round-trips them safely unquoted, but the
guided editor parses the frontmatter with js-yaml, which reads an unquoted
`01325387700` as the number `1325387700` (leading zero dropped) and then fails
the schema's `string` type on save. Quoting keeps every YAML parser honest.
"""

from llmstxt_core.open_org.converter import json_to_markdown, markdown_to_json

from tests.open_org._examples import PROFILE_MD


def test_numeric_looking_string_scalars_are_quoted():
    md = json_to_markdown(
        {
            "schema_version": "open-org/v0.1",
            "identity": {
                "registration": {"number": "1135126"},
                "contact": {"phone": "01325387700"},
            },
        },
        kind="profile",
    )
    assert "phone: '01325387700'" in md
    assert "number: '1135126'" in md


def test_phone_round_trips_as_string_with_leading_zero():
    base = markdown_to_json(PROFILE_MD, kind="profile")
    base.setdefault("identity", {}).setdefault("contact", {})["phone"] = "01325387700"

    md = json_to_markdown(base, kind="profile")
    assert "phone: '01325387700'" in md  # quoted in the rendered markdown

    back = markdown_to_json(md, kind="profile")  # also validates
    assert back["identity"]["contact"]["phone"] == "01325387700"
    assert isinstance(back["identity"]["contact"]["phone"], str)


def test_normal_text_is_not_over_quoted():
    md = json_to_markdown(
        {"schema_version": "open-org/v0.1", "identity": {"name": "Tandem"}},
        kind="profile",
    )
    assert "name: Tandem" in md  # plain words stay unquoted
