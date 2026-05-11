"""Round-trip identity tests for the converter.

The load-bearing invariant for the editor: starting from a valid Open Org
payload, running ``json_to_markdown`` then ``markdown_to_json`` must yield the
same payload. Two-cycle convergence is also asserted — md → json → md → json
yields identical json on both extractions, so any non-determinism is caught.
"""

from llmstxt_core.open_org.converter import json_to_markdown, markdown_to_json
from llmstxt_core.open_org.validator import validate_for_kind

from tests.open_org._examples import IDEA_MD, PROFILE_MD, STRATEGY_MD


def _round_trip(md: str, kind: str) -> dict:
    """Run md → json → md → json and assert the two json snapshots match."""
    json_a = markdown_to_json(md, kind=kind)
    md_b = json_to_markdown(json_a, kind=kind)
    json_b = markdown_to_json(md_b, kind=kind)
    assert json_a == json_b, (
        f"round-trip diverged for {kind}: "
        f"first={json_a!r} second={json_b!r}"
    )
    # Also assert validation still passes after the round-trip.
    validate_for_kind(json_b, kind=kind)
    return json_a


def test_round_trip_profile():
    payload = _round_trip(PROFILE_MD, kind="profile")
    # Sanity: round-tripped payload still has the expected shape.
    assert payload["identity"]["name"] == "Riverside Community Trust"
    assert payload["values"][0] == "Everyone deserves connection"


def test_round_trip_strategy():
    payload = _round_trip(STRATEGY_MD, kind="strategy")
    assert len(payload["not_doing"]) == 2
    assert payload["not_doing"][0]["title"] == "Opening a food bank."
    assert len(payload["tensions"]) == 1
    assert payload["learning"]["what_changed"][0]["source"] == "programme_failure"


def test_round_trip_idea():
    payload = _round_trip(IDEA_MD, kind="idea")
    assert payload["summary"].startswith("A network")
    assert payload["detail"].startswith("Each kitchen")


def test_round_trip_strips_purely_decorative_whitespace():
    """Adding extra blank lines between sections must not alter the JSON."""
    chatty = PROFILE_MD.replace("## Mission\n\nSupporting", "## Mission\n\n\n\nSupporting")
    canonical = markdown_to_json(PROFILE_MD, kind="profile")
    chatty_payload = markdown_to_json(chatty, kind="profile")
    assert chatty_payload == canonical


def test_round_trip_handles_section_reordering():
    """Reordering body sections in the source markdown must not alter the JSON."""
    # Build a reordered variant by hand (Values before Mission).
    parts = PROFILE_MD.split("---", 2)
    frontmatter, body = parts[1], parts[2]
    reordered_body = (
        "\n## Values\n\n- Everyone deserves connection\n- Listen before you act\n- Be honest about failure\n\n"
        "## Mission\n\nSupporting isolated older people to build social connections.\n\n"
        "## Theory of change\n\nWe believe that loneliness is driven by the erosion of everyday social infrastructure.\n\n"
        "## Culture\n\nWe're a small team that moves fast and learns publicly.\n"
    )
    reordered = f"---{frontmatter}---{reordered_body}"
    canonical = markdown_to_json(PROFILE_MD, kind="profile")
    reordered_payload = markdown_to_json(reordered, kind="profile")
    assert reordered_payload == canonical
