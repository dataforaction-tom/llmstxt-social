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
