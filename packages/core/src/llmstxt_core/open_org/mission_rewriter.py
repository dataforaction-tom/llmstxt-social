"""Rewrite Charity Commission ``activities`` text into a plain-language summary.

The CC ``activities`` field is often jargon-heavy ("the provision of services
to advance education..."). The Open Org schema's ``mission.summary`` is short,
plain language for humans and machine readers; we ask Claude to do the
rewrite. Hard-cap at 500 characters to satisfy the schema even if the model
runs long.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llmstxt_core.llm import CachedAnthropic, Usage, system_block


MISSION_SUMMARY_MAX_CHARS = 500


_SYSTEM_PROMPT = (
    "You rewrite UK charity descriptions into one short paragraph of plain "
    "English. The audience is a curious member of the public, not a regulator. "
    "Rules:\n"
    "- One paragraph, under 500 characters.\n"
    "- Plain language; no legal or sector jargon.\n"
    "- Active voice.\n"
    "- Describe what the charity does and who it helps.\n"
    "- No marketing fluff, no exclamation marks.\n"
    "- Return only the rewritten summary, no preamble or quotes."
)


@dataclass
class MissionRewriteResult:
    summary: str = ""
    usage: Usage = field(default_factory=Usage)


def _clean(text: str) -> str:
    cleaned = text.strip()
    # Models occasionally wrap the output in quotes; strip a single matching pair.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'", "`"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def rewrite_mission_summary(
    *,
    client: CachedAnthropic,
    activities_text: str,
    model: str | None = None,
) -> MissionRewriteResult:
    """Return a plain-language mission summary rewritten from ``activities_text``.

    Returns an empty result without calling the model when the input is blank.
    Output is hard-truncated to :data:`MISSION_SUMMARY_MAX_CHARS` to satisfy
    the Open Org schema.
    """
    text = (activities_text or "").strip()
    if not text:
        return MissionRewriteResult()

    user = (
        "Rewrite the charity description below as a plain-English mission summary.\n\n"
        f"Charity description:\n{text}"
    )

    result = client.complete(
        messages=[{"role": "user", "content": user}],
        system=[system_block(_SYSTEM_PROMPT)],
        model=model,
        temperature=0,
        max_tokens=600,
    )

    summary = _clean(result.text)
    if len(summary) > MISSION_SUMMARY_MAX_CHARS:
        summary = summary[:MISSION_SUMMARY_MAX_CHARS].rstrip()

    return MissionRewriteResult(summary=summary, usage=result.usage)


__all__ = [
    "MISSION_SUMMARY_MAX_CHARS",
    "MissionRewriteResult",
    "rewrite_mission_summary",
]
