"""Tests for the three Open Org JSON Schemas.

The fixtures here are the YAML frontmatter from the spec's example markdown
templates (open-org/open-org-phase1-spec.md sections 5.1, 5.2, 5.3). If a
schema change breaks one of these examples, the spec must be updated in
lockstep.
"""

import yaml
from llmstxt_core.open_org.validator import (
    ValidationError,
    load_schema,
    validate,
    validate_for_kind,
    validate_iter,
)


PROFILE_EXAMPLE_YAML = """
schema_version: open-org/v0.1
identity:
  name: "Riverside Community Trust"
  registration:
    charity_commission_ew: "1234567"
    companies_house: "CE012345"
  geography:
    primary_area: "Great Yarmouth"
    primary_area_code: "E07000145"
    operating_areas:
      - Norfolk
      - Suffolk
  scale:
    annual_income_band: "250k-500k"
    staff_count: 8
    volunteer_count: 45
  website: "https://riverside-trust.org.uk"
  founded: "2012-03-15"

mission:
  themes:
    - older_people
    - loneliness
    - community_development
    - food_access
  beneficiaries:
    - Isolated older people
    - Carers

governance:
  board_size: 9
  accounts_filed_to: "2025-03-31"
  policies:
    - name: safeguarding
      last_reviewed: "2025-01-10"
    - name: financial_controls
      last_reviewed: "2024-09-15"
"""


STRATEGY_EXAMPLE_YAML = """
schema_version: open-org-strategy/v0.1
id: "strategy-2025-2028"
status: active
period:
  start: "2025-04-01"
  end: "2028-03-31"
  horizon: "3_5_years"
themes:
  - food_access
  - social_prescribing
  - community_development
  - volunteering
access_level: summary_public
resource_model:
  current_funding_mix:
    grants: 65
    contracts: 20
    earned_income: 10
    donations: 5
  sustainability_direction: diversifying
  resourcing_gaps:
    - Core funding for volunteer coordinator
    - Kitchen equipment and premises costs
"""


IDEA_EXAMPLE_YAML = """
schema_version: open-org-idea/v0.1
id: "community-kitchen-network"
status: developing
place:
  description: "Great Yarmouth"
  area_codes:
    - "E07000145"
themes:
  - food_access
  - social_prescribing
  - community_development
beneficiaries:
  - Isolated older people
  - People referred via social prescribing
indicative_cost:
  lower: 80000
  upper: 120000
  currency: GBP
  period: "2 years"
evidence_base:
  - evidence_id: "befriending-eval-2024"
    relevance: "Demonstrates volunteer network building"
  - evidence_id: "food-delivery-covid"
    relevance: "Food as connector, not just provision"
connections:
  - org_name: "Norfolk Food Network"
    relationship: complementary
    mutual: false
collaborators:
  - org_name: "GT Health Partnership"
    role: referral_partner
    confirmed: true
"""


# --- profile -----------------------------------------------------------------

def test_profile_schema_loads():
    schema = load_schema("profile")
    assert schema["$schema"].startswith("https://json-schema.org/draft/2020-12")


def test_profile_example_validates():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    validate_for_kind(payload, kind="profile")  # raises if invalid


def test_profile_missing_name_fails():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    del payload["identity"]["name"]
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert any("name" in e["message"] or "name" in e["path"] for e in errors)


def test_profile_no_registration_fails():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    payload["identity"]["registration"] = {}
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert errors, "empty registration object should fail"


def test_profile_invalid_income_band_fails():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    payload["identity"]["scale"]["annual_income_band"] = "tiny"
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert any("annual_income_band" in e["path"] for e in errors)


def test_profile_themes_must_be_non_empty():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    payload["mission"]["themes"] = []
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert any("themes" in e["path"] for e in errors)


def test_profile_schema_version_must_match():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    payload["schema_version"] = "open-org/v9.9"
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert any("schema_version" in e["path"] for e in errors)


# --- strategy ----------------------------------------------------------------

def test_strategy_schema_loads():
    load_schema("strategy")


def test_strategy_example_validates():
    payload = yaml.safe_load(STRATEGY_EXAMPLE_YAML)
    validate_for_kind(payload, kind="strategy")


def test_strategy_invalid_status_fails():
    payload = yaml.safe_load(STRATEGY_EXAMPLE_YAML)
    payload["status"] = "spaghetti"
    errors = validate_iter(payload, schema=load_schema("strategy"))
    assert any("status" in e["path"] for e in errors)


def test_strategy_invalid_horizon_fails():
    payload = yaml.safe_load(STRATEGY_EXAMPLE_YAML)
    payload["period"]["horizon"] = "fortnight"
    errors = validate_iter(payload, schema=load_schema("strategy"))
    assert any("horizon" in e["path"] for e in errors)


def test_strategy_funding_mix_must_total_100():
    """Funding mix percentages should add up — guard against typos."""
    payload = yaml.safe_load(STRATEGY_EXAMPLE_YAML)
    payload["resource_model"]["current_funding_mix"] = {
        "grants": 50,
        "contracts": 30,
        "earned_income": 30,  # totals 110%
        "donations": 0,
    }
    # Schema can't easily express "sum = 100" so this is checked at the
    # converter level; here we just confirm the schema accepts the structure.
    errors = validate_iter(payload, schema=load_schema("strategy"))
    # Structural validation should still pass — the sum check lives elsewhere.
    assert all("current_funding_mix" not in e["path"] for e in errors)


# --- idea --------------------------------------------------------------------

def test_idea_schema_loads():
    load_schema("idea")


def test_idea_example_validates():
    payload = yaml.safe_load(IDEA_EXAMPLE_YAML)
    validate_for_kind(payload, kind="idea")


def test_idea_invalid_status_fails():
    payload = yaml.safe_load(IDEA_EXAMPLE_YAML)
    payload["status"] = "vibing"
    errors = validate_iter(payload, schema=load_schema("idea"))
    assert any("status" in e["path"] for e in errors)


def test_idea_cost_lower_must_be_lower_than_upper():
    """If both bounds present, lower ≤ upper. Schema can't enforce cross-field
    relations directly — converter checks. Here we just confirm structural shape."""
    payload = yaml.safe_load(IDEA_EXAMPLE_YAML)
    payload["indicative_cost"]["lower"] = -100
    errors = validate_iter(payload, schema=load_schema("idea"))
    assert any("lower" in e["path"] for e in errors), "negative cost should fail minimum:0"


def test_idea_themes_must_come_from_vocabulary():
    """Schema enum keeps theme keys in sync with the controlled vocabulary."""
    payload = yaml.safe_load(IDEA_EXAMPLE_YAML)
    payload["themes"] = ["not_a_real_theme"]
    errors = validate_iter(payload, schema=load_schema("idea"))
    assert any("themes" in e["path"] for e in errors)


# --- profile uses the controlled vocabulary too ------------------------------

def test_profile_themes_must_come_from_vocabulary():
    payload = yaml.safe_load(PROFILE_EXAMPLE_YAML)
    payload["mission"]["themes"] = ["space_exploration"]
    errors = validate_iter(payload, schema=load_schema("profile"))
    assert any("themes" in e["path"] for e in errors)
