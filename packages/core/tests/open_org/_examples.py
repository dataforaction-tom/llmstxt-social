"""Shared fixtures (markdown documents) used across converter test files.

Not a test module — name starts with ``_`` so pytest won't collect it.
Mirrors the spec section 5 templates and is the canonical worked example
for round-trip identity tests.
"""

PROFILE_MD = """---
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
---

## Mission

Supporting isolated older people to build social connections.

## Theory of change

We believe that loneliness is driven by the erosion of everyday social infrastructure.

## Culture

We're a small team that moves fast and learns publicly.

## Values

- Everyone deserves connection
- Listen before you act
- Be honest about failure
"""


STRATEGY_MD = """---
schema_version: open-org-strategy/v0.1
id: "strategy-2025-2028"
status: active
period:
  start: "2025-04-01"
  end: "2028-03-31"
  horizon: "3_5_years"
themes:
  - food_access
  - community_development
access_level: summary_public
---

## Summary

Three-year plan to build a place-based food system in Great Yarmouth.

## Not doing

- **Opening a food bank.** Transactional food provision can undermine dignity.
- **Expanding to Norwich.** Depth in one place matters more than breadth across two.

## Tensions

- **Growth vs depth.** Three kitchens is ambitious for an organisation our size.

## Learning

- Monthly check-ins lifted volunteer retention from 40% to 80%.
  *Source: programme_failure*
- Food is a connector, not just a need.
"""


IDEA_MD = """---
schema_version: open-org-idea/v0.1
id: "community-kitchen-network"
status: developing
themes:
  - food_access
  - community_development
place:
  description: "Great Yarmouth"
  area_codes:
    - "E07000145"
indicative_cost:
  lower: 80000
  upper: 120000
  currency: GBP
  period: "2 years"
---

## Summary

A network of three community kitchens across Great Yarmouth.

## The detail

Each kitchen runs three sessions per week. Pay-what-you-can meals.
"""
