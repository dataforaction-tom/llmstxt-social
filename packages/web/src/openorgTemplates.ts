/**
 * Blank Open Org templates for "New strategy" / "New idea" flows.
 *
 * Per spec section 2: templates carry `<!-- guidance -->` comments that the
 * server-side converter strips on save. They give an organisation a
 * scaffolded place to write without having to learn the schema or use the
 * chat creator.
 */

export const NEW_STRATEGY_TEMPLATE = `---
schema_version: open-org-strategy/v0.1
id: "draft-2025-2028"     # slug — short, dash-separated, the URL-stable identifier
status: draft              # draft | active | archived
period:
  start: ""                # YYYY-MM-DD — when does this strategy start?
  end: ""                  # YYYY-MM-DD — when does it end?
  horizon: "3_5_years"     # 1_year | 2_3_years | 3_5_years | 5_10_years
themes:                    # pick from the controlled vocabulary
  - food_access
priorities:                # the 2-5 things you're focusing on (frontmatter only)
  - title: "[replace with your priority title]"
    narrative: ""          # one sentence on why this matters
    maturity: "emerging"   # seed | emerging | established | mature
    success_indicators:    # how you'll know it's working
      - ""
access_level: summary_public
---

## Summary

<!-- What is this organisation trying to become or achieve over this
     period? Write it in plain language, as if explaining to someone who
     knows nothing about you. 2-4 sentences. -->

## Not doing

<!-- What have you decided NOT to do, and why?
     This is often more revealing than what you will do. Be honest.
     Format each as: "- **Short label.** Description and reasoning." -->

## Tensions

<!-- What trade-offs are you holding?
     Growth vs depth? Earned income vs mission?
     Same format: "- **Short label.** Description." -->

## Learning

<!-- What failed? What changed? What surprised you?
     How does this organisation handle things going wrong?
     Add a *Source: type* tag at the end of each item (e.g.
     *Source: programme_failure*, *Source: pandemic_response*). -->
`;

export const NEW_IDEA_TEMPLATE = `---
schema_version: open-org-idea/v0.1
id: "your-idea-slug"      # short, dash-separated identifier
status: seed              # seed | developing | shaped | delivered | archived
themes:
  - food_access
place:
  description: ""         # where would this happen?
indicative_cost:
  lower: 0
  upper: 0
  currency: GBP
  period: ""              # e.g. "1 year", "18 months"
---

## Summary

<!-- What's the idea? 1-2 sentences. -->

## The detail

<!-- - What would happen in practice?
     - Who would it serve?
     - What evidence supports this approach?
     - Who would you collaborate with? -->
`;

export type TemplateKind = 'strategy' | 'idea';

export function templateFor(kind: TemplateKind): string {
  return kind === 'strategy' ? NEW_STRATEGY_TEMPLATE : NEW_IDEA_TEMPLATE;
}

/**
 * Profile markdown template with guided comments.
 *
 * Used by the editor when an organisation first claims/generates a profile.
 * Comments are stripped on save by the server-side converter.
 */
export const NEW_PROFILE_TEMPLATE = `---
schema_version: open-org/v0.1

identity:
  name: ""                       # your organisation's name
  registration:
    charity_commission_ew: ""     # your CC number (or companies_house / oscr / ccni / other)
  geography:
    primary_area: ""             # e.g. "Great Yarmouth"
  website: ""
  founded: ""

mission:
  summary: ""                    # 1-2 sentences on what you do
  themes:                         # pick from the controlled vocabulary
    - food_access
  beneficiaries:
    - ""
---


## Mission

<!-- One or two sentences on what your organisation does and who it serves. -->

## Theory of change

<!-- How do your activities lead to the change you want to see? -->

## Culture

<!-- How do you work? What's it like inside the organisation? -->

## Values

<!-- 3-5 bullets — the principles that guide your decisions. -->

- Everyone deserves connection
- Listen before you act

## Evidence

<!-- List your evidence items here. Each one gets a ### heading.
     Evidence types: evaluation, outcome_data, annual_report, case_study, learning_reflection, external_research, other
     This is what you've done and learned — the longitudinal track record
     that funders can browse instead of reading a one-shot application. -->

### eval-2024: [Title]

<!-- What did you evaluate? What did you find? -->

- **type:** evaluation
- **date:** 2024-06-01
- **themes:** food_access, social_prescribing
- **outcomes:**
  - 500 meals served per month
  - 40% reduction in loneliness scores
`;
