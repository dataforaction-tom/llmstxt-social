"""Map Charity Commission text to Open Org theme keys via Claude tool_use.

The Open Org schema accepts an array of theme keys from a fixed 30-entry
vocabulary (``data/themes.json``). The CC API gives us free-form
``charitable_objects`` and ``activities`` text. We ask Claude to tag the text
against the vocabulary and only accept matches at or above a confidence
threshold (default 0.7, per the spec).

We use the Anthropic tool_use API rather than prose-parsing because the model
guarantees the response shape — there is no fallback to regex-fishing through
text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llmstxt_core.llm import (
    CachedAnthropic,
    Usage,
    extract_tool_input,
    system_block,
)
from llmstxt_core.llm import _usage_from_sdk  # noqa: PLC2701 — internal helper reuse
from llmstxt_core.open_org.themes import load_themes, theme_keys


DEFAULT_CONFIDENCE_THRESHOLD = 0.7
TOOL_NAME = "emit_theme_matches"


@dataclass
class ThemeExtractionResult:
    themes: list[str] = field(default_factory=list)
    flagged: list[dict] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


def _build_tool_spec() -> dict:
    return {
        "name": TOOL_NAME,
        "description": (
            "Emit the Open Org theme keys that apply to a charity, with a "
            "confidence score for each match. Only use keys from the supplied "
            "controlled vocabulary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "matches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "reason": {"type": "string"},
                        },
                        "required": ["theme", "confidence"],
                    },
                }
            },
            "required": ["matches"],
        },
    }


def _vocabulary_block_text() -> str:
    """A long, stable text block describing the theme vocabulary.

    Stable across calls so prompt caching pays off (Anthropic minimum is
    1024 tokens for the cache to apply on Sonnet/Opus).
    """
    lines = [
        "You are mapping UK charity descriptions to a controlled vocabulary "
        "of themes for the Open Org schema. Only use the keys listed below. "
        "Each entry has a key, a human label, and a description; rely on the "
        "description for boundary cases."
    ]
    for theme in load_themes():
        key = theme.get("key", "")
        label = theme.get("label", "")
        desc = theme.get("description", "")
        lines.append(f"- {key} | {label} | {desc}")

    # v0.2.3: negative-match rules. The v0.1 baseline showed `education`
    # over-applied because awareness/training language appears in many
    # charities' CC text even when education isn't their primary mission.
    lines.append("")
    lines.append("## Negative-match rules")
    lines.append(
        "- **education**: only apply when education is the charity's "
        "primary activity (schools, tutoring, formal learning, literacy, "
        "scholarships). Do NOT apply when training, awareness-raising, or "
        "professional development is incidental to a different mission "
        "(e.g. mental health charities that run training for clinicians; "
        "food banks that run cooking workshops; refugees charities that "
        "run language classes). When in doubt, leave education off and "
        "let the primary theme stand."
    )

    # v0.2.2: worked examples for themes the v0.1 baseline missed on
    # well-known charities (Trussell, Shelter, Mind, NSPCC, Macmillan, BRC,
    # Oxfam). Each example pairs a charity-style activity snippet with the
    # theme it should match — concrete anchors the model can pattern-match
    # against rather than relying on the vocabulary description alone.
    lines.append("")
    lines.append("## Worked examples")
    lines.append(
        "These examples show the correct theme key for common charity "
        "activities. When you see similar language in the input, prefer the "
        "matching key. Examples are *positive matches*, not exhaustive — "
        "many activities qualify for more than one key."
    )
    examples = [
        ("food_access",
         "A network of food banks distributing emergency food parcels to "
         "people in crisis. Surplus-food redistribution. A community fridge "
         "or pantry. Holiday meal provision for children."),
        ("housing_and_homelessness",
         "Supporting rough sleepers off the streets. Running a hostel or "
         "night shelter. Tenancy advice and eviction prevention. Campaigning "
         "for affordable housing. Outreach to people sleeping rough."),
        ("mental_health",
         "Mental health support services — counselling, talking therapies, "
         "peer support. Anxiety and depression helplines. Suicide prevention. "
         "Crisis cafes. Support for people with severe and enduring mental "
         "illness. Use mental_health (NOT health) for anything that's "
         "explicitly about psychological wellbeing or mental ill-health."),
        ("domestic_abuse",
         "Refuges and safehouses for people fleeing abusive relationships. "
         "Helplines for survivors of domestic abuse. Perpetrator behaviour-"
         "change programmes. Independent domestic violence advisors."),
        ("children_and_young_people",
         "Youth clubs, mentoring schemes for young people, after-school "
         "programmes, helplines for children. Safeguarding children. "
         "Activities aimed at under-18s or care leavers. Use this key "
         "alongside more specific ones (e.g. children + education)."),
        ("refugees_and_migration",
         "Supporting refugees and asylum seekers. Migrant integration "
         "services. Legal advice on immigration. Resettlement programmes. "
         "Language classes for new arrivals."),
        ("loneliness",
         "Befriending services, social prescribing for isolated people, "
         "telephone friendship lines, community lunch clubs aimed at "
         "reducing social isolation, particularly among older adults."),
        ("families_and_carers",
         "Support for unpaid carers — respite, peer groups, training. "
         "Family services, parenting support, carer assessments. Help for "
         "kinship carers and care-experienced families."),
        ("poverty_and_financial_inclusion",
         "Debt advice, welfare rights, benefits advocacy, financial "
         "education, emergency grants for people in hardship, fuel-poverty "
         "support, money-management coaching."),
        ("disability",
         "Services for disabled people — accessibility advocacy, supported "
         "living, day services, equipment loan, independent living advice. "
         "Both physical and learning disabilities count here."),
    ]
    for key, snippet in examples:
        lines.append(f"- **{key}**: {snippet}")
    return "\n".join(lines)


def extract_themes(
    *,
    client: CachedAnthropic,
    objects_text: str,
    activities_text: str,
    website_text: str = "",
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    model: str | None = None,
) -> ThemeExtractionResult:
    """Tag CC text against the Open Org theme vocabulary.

    Returns themes accepted at or above ``confidence_threshold`` plus a
    ``flagged`` list (matches the model is less sure about). The caller can
    surface flagged items for human review.

    ``website_text`` is optional content from the charity's own site. The v0.1
    baseline run showed CC ``who_what_where`` classifications are too sparse
    for orgs like Trussell Trust and Shelter; passing the homepage + about
    page text alongside CC fields closes the gap.
    """
    objects_text = (objects_text or "").strip()
    activities_text = (activities_text or "").strip()
    website_text = (website_text or "").strip()
    if not objects_text and not activities_text and not website_text:
        return ThemeExtractionResult()

    system = [
        system_block(
            "You analyse charity descriptions and emit theme tags from the "
            "Open Org controlled vocabulary. You must call the "
            f"'{TOOL_NAME}' tool exactly once. Only use keys from the "
            "vocabulary in your context. Confidence is your honest estimate "
            "from 0 to 1.",
        ),
        system_block(_vocabulary_block_text(), cache=True),
    ]

    user_message_parts = [
        "Charity-supplied text follows. Identify which Open Org themes apply.",
        "",
        f"Charitable objects:\n{objects_text or '(not supplied)'}",
        "",
        f"Activities:\n{activities_text or '(not supplied)'}",
    ]
    if website_text:
        # The website is the charity's voice; weight it equally with CC text.
        # Truncate to keep the prompt within a sensible cost envelope.
        user_message_parts.extend(
            [
                "",
                f"Website content (homepage / about pages):\n{website_text[:8000]}",
            ]
        )
    user_message = "\n".join(user_message_parts)

    result = client.complete(
        messages=[{"role": "user", "content": user_message}],
        system=system,
        model=model,
        tools=[_build_tool_spec()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        temperature=0,
    )

    payload = extract_tool_input(result.raw, TOOL_NAME)
    if not payload:
        # Model returned prose instead of a tool call. Nothing to do — the
        # caller can retry or accept the empty result.
        return ThemeExtractionResult(usage=result.usage)

    valid_keys = theme_keys()
    accepted: list[str] = []
    flagged: list[dict] = []
    seen: set[str] = set()
    for match in payload.get("matches") or []:
        if not isinstance(match, dict):
            continue
        key = match.get("theme")
        confidence = match.get("confidence")
        if not isinstance(key, str) or not isinstance(confidence, (int, float)):
            continue
        if key not in valid_keys:
            continue
        if key in seen:
            continue
        seen.add(key)
        if confidence >= confidence_threshold:
            accepted.append(key)
        else:
            flagged.append(
                {
                    "theme": key,
                    "confidence": float(confidence),
                    "reason": match.get("reason", ""),
                }
            )

    return ThemeExtractionResult(
        themes=accepted,
        flagged=flagged,
        usage=result.usage,
    )


__all__ = [
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "TOOL_NAME",
    "ThemeExtractionResult",
    "extract_themes",
]
