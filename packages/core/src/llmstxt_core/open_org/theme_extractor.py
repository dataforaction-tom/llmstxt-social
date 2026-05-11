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
