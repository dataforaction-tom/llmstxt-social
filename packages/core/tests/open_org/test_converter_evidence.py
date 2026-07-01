"""Tests for the evidence section in the profile converter.

The evidence layer is a first-class top-level ``evidence`` array on the
profile, with each item rendered as a ``### {evidence_id}: {title}``
subsection inside a ``## Evidence`` body section.
"""

import pytest

from llmstxt_core.open_org.converter import json_to_markdown, markdown_to_json


# Minimal valid profile frontmatter for round-trip tests.
_PROFILE_FM = """---
schema_version: open-org/v0.1

identity:
  name: "Riverside Community Trust"
  registration:
    charity_commission_ew: "1234567"

mission:
  themes:
    - older_people
---


## Mission

Supporting isolated older people to build social connections.
"""


def _profile_md_with_evidence(evidence_body: str) -> str:
    return f"{_PROFILE_FM}\n{evidence_body}"


# --- markdown_to_json --------------------------------------------------------

def test_evidence_section_parses_into_array():
    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

We evaluated the befriending programme across three sites.

- **type:** evaluation
- **date:** 2024-06-01
- **url:** https://riverside.example/eval-2024.pdf
- **themes:** food_access, social_prescribing
- **outcomes:**
  - 500 meals served per month
  - 40% reduction in loneliness scores
"""
    )
    payload = markdown_to_json(md, kind="profile")
    assert "evidence" in payload
    assert len(payload["evidence"]) == 1
    item = payload["evidence"][0]
    assert item["evidence_id"] == "eval-2024"
    assert item["title"] == "Annual Evaluation"
    assert item["evidence_type"] == "evaluation"
    assert item["date"] == "2024-06-01"
    assert item["url"] == "https://riverside.example/eval-2024.pdf"
    assert item["themes"] == ["food_access", "social_prescribing"]
    assert item["outcomes"] == [
        "500 meals served per month",
        "40% reduction in loneliness scores",
    ]
    assert "befriending programme" in item["description"]


def test_evidence_section_with_multiple_items():
    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

First evaluation.

- **type:** evaluation

### case-001: Kitchen case study

A case study of the community kitchen.

- **type:** case_study
- **date:** 2024-03-15
"""
    )
    payload = markdown_to_json(md, kind="profile")
    assert len(payload["evidence"]) == 2
    assert payload["evidence"][0]["evidence_id"] == "eval-2024"
    assert payload["evidence"][1]["evidence_id"] == "case-001"
    assert payload["evidence"][1]["evidence_type"] == "case_study"


def test_evidence_section_no_items_produces_empty_array():
    md = _profile_md_with_evidence("## Evidence\n\nNo evidence yet.")
    payload = markdown_to_json(md, kind="profile")
    assert payload["evidence"] == []


def test_evidence_section_with_minimal_item():
    md = _profile_md_with_evidence(
        """## Evidence

### rep-2023: Annual Report 2023
"""
    )
    payload = markdown_to_json(md, kind="profile")
    assert len(payload["evidence"]) == 1
    item = payload["evidence"][0]
    assert item["evidence_id"] == "rep-2023"
    assert item["title"] == "Annual Report 2023"
    # Optional fields absent.
    assert "evidence_type" not in item
    assert "date" not in item
    assert "description" not in item


def test_evidence_validates_against_schema():
    from llmstxt_core.open_org.validator import validate_for_kind

    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

We evaluated the befriending programme.

- **type:** evaluation
- **date:** 2024-06-01
"""
    )
    payload = markdown_to_json(md, kind="profile")
    validate_for_kind(payload, kind="profile")


# --- round-trip --------------------------------------------------------------

def test_evidence_round_trip_all_fields():
    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

We evaluated the befriending programme across three sites.

- **type:** evaluation
- **date:** 2024-06-01
- **url:** https://riverside.example/eval-2024.pdf
- **themes:** food_access, social_prescribing
- **outcomes:**
  - 500 meals served per month
  - 40% reduction in loneliness scores
"""
    )
    json_a = markdown_to_json(md, kind="profile")
    md_b = json_to_markdown(json_a, kind="profile")
    json_b = markdown_to_json(md_b, kind="profile")
    assert json_a == json_b, f"round-trip diverged:\n--- md_b ---\n{md_b}\n--- json_a ---\n{json_a}\n--- json_b ---\n{json_b}"


def test_evidence_round_trip_minimal_item():
    md = _profile_md_with_evidence(
        """## Evidence

### rep-2023: Annual Report 2023
"""
    )
    json_a = markdown_to_json(md, kind="profile")
    md_b = json_to_markdown(json_a, kind="profile")
    json_b = markdown_to_json(md_b, kind="profile")
    assert json_a == json_b


def test_evidence_round_trip_multiple_items():
    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

First evaluation.

- **type:** evaluation

### case-001: Kitchen case study

A case study of the community kitchen.

- **type:** case_study
- **date:** 2024-03-15
- **outcomes:**
  - 80% retention
"""
    )
    json_a = markdown_to_json(md, kind="profile")
    md_b = json_to_markdown(json_a, kind="profile")
    json_b = markdown_to_json(md_b, kind="profile")
    assert json_a == json_b


def test_evidence_round_trip_empty_section():
    md = _profile_md_with_evidence("## Evidence\n\nNo evidence yet.")
    json_a = markdown_to_json(md, kind="profile")
    md_b = json_to_markdown(json_a, kind="profile")
    json_b = markdown_to_json(md_b, kind="profile")
    assert json_a == json_b


def test_profile_without_evidence_section_has_no_evidence_key():
    # The base profile markdown (no ## Evidence section) should not produce
    # an evidence key in the JSON.
    payload = markdown_to_json(_PROFILE_FM.strip() + "\n", kind="profile")
    assert "evidence" not in payload


def test_evidence_section_does_not_break_other_sections():
    """Adding an evidence section after existing sections keeps Mission etc."""
    md = _profile_md_with_evidence(
        """## Evidence

### eval-2024: Annual Evaluation

- **type:** evaluation
"""
    )
    payload = markdown_to_json(md, kind="profile")
    assert payload["mission"]["summary"].startswith("Supporting")
    assert payload["identity"]["name"] == "Riverside Community Trust"
    assert len(payload["evidence"]) == 1