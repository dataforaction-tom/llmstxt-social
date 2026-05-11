"""Phase-1 real-world testing harness for the profile generator.

Reads a YAML corpus of UK charity numbers, runs each through
:func:`generate_profile_from_charity_number`, collects per-charity outcomes,
and renders a markdown report the operator reads before iterating to schema
v0.2.

The harness is operator-driven (CLI subcommand). It hits real CC + Anthropic
APIs when wired with production collaborators; tests inject a fake generator
to keep them offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

import yaml

from llmstxt_core.llm import CachedAnthropic, Usage
from llmstxt_core.open_org.generator import (
    GenerationResult,
    ProfileGenerationError,
    generate_profile_from_charity_number,
)


_CHARITY_NUMBER_RE = re.compile(r"^[0-9]{6,8}$")


class InvalidCorpusError(ValueError):
    """Raised when the corpus YAML can't be parsed or has bad entries."""


@dataclass
class CorpusEntry:
    charity_number: str
    name: str | None = None
    notes: str | None = None


@dataclass
class CharityResult:
    entry: CorpusEntry
    success: bool
    org_id: str | None
    markdown_length: int
    themes: list[str]
    flagged_themes: list[dict]
    usage: Usage
    error: str | None


GeneratorFn = Callable[..., Awaitable[GenerationResult]]


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------


def load_corpus(path: Path) -> list[CorpusEntry]:
    """Load and validate a corpus YAML file. Returns ``[]`` for an empty file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise InvalidCorpusError(
            f"corpus YAML at {path} must be a mapping with a 'charities' key"
        )
    items = raw.get("charities") or []
    if not isinstance(items, list):
        raise InvalidCorpusError("'charities' must be a list")

    entries: list[CorpusEntry] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise InvalidCorpusError(f"corpus entry #{index} must be a mapping")
        number = item.get("charity_number")
        if not isinstance(number, str) or not _CHARITY_NUMBER_RE.match(number):
            raise InvalidCorpusError(
                f"corpus entry #{index}: 'charity_number' must match {_CHARITY_NUMBER_RE.pattern!r}"
            )
        entries.append(
            CorpusEntry(
                charity_number=number,
                name=item.get("name"),
                notes=item.get("notes"),
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Run + report
# ---------------------------------------------------------------------------


async def run_corpus(
    entries: list[CorpusEntry],
    *,
    anthropic_client: CachedAnthropic,
    cc_api_key: str | None,
    generator: GeneratorFn | None = None,
) -> list[CharityResult]:
    """Run the profile generator against each corpus entry.

    Exceptions are caught per entry so one bad charity doesn't kill the batch.
    """
    gen = generator or generate_profile_from_charity_number
    results: list[CharityResult] = []

    for entry in entries:
        try:
            result = await gen(
                entry.charity_number,
                anthropic_client=anthropic_client,
                cc_api_key=cc_api_key,
            )
        except ProfileGenerationError as exc:
            results.append(_failure(entry, str(exc)))
            continue
        except Exception as exc:  # noqa: BLE001 — surface any oddity, don't crash the run
            results.append(_failure(entry, f"{exc.__class__.__name__}: {exc}"))
            continue

        themes = list((result.json_payload.get("mission") or {}).get("themes") or [])
        results.append(
            CharityResult(
                entry=entry,
                success=True,
                org_id=result.org_id,
                markdown_length=len(result.markdown or ""),
                themes=themes,
                flagged_themes=list(result.flagged_themes or []),
                usage=result.total_usage,
                error=None,
            )
        )
    return results


def _failure(entry: CorpusEntry, message: str) -> CharityResult:
    return CharityResult(
        entry=entry,
        success=False,
        org_id=None,
        markdown_length=0,
        themes=[],
        flagged_themes=[],
        usage=Usage(),
        error=message,
    )


def render_report(results: list[CharityResult], *, run_at: datetime) -> str:
    """Render the per-corpus markdown report."""
    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    total_input = sum(r.usage.input_tokens for r in results)
    total_output = sum(r.usage.output_tokens for r in results)

    lines: list[str] = []
    lines.append(f"# Real-world corpus run — {run_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- {len(results)} charities in corpus")
    lines.append(f"- {succeeded} succeeded")
    lines.append(f"- {failed} failed")
    lines.append(f"- Total Anthropic usage: {total_input} input tokens, {total_output} output tokens")
    lines.append("")

    if not results:
        lines.append("_No entries in the corpus yet. Add charity numbers to the corpus file._")
        lines.append("")
        return "\n".join(lines)

    if failed:
        lines.append("## Common failure modes")
        lines.append("")
        failure_messages: dict[str, int] = {}
        for r in results:
            if not r.success and r.error:
                key = r.error.splitlines()[0][:120]
                failure_messages[key] = failure_messages.get(key, 0) + 1
        for message, count in sorted(failure_messages.items(), key=lambda x: -x[1]):
            lines.append(f"- ({count}×) {message}")
        lines.append("")

    lines.append("## Per-charity results")
    lines.append("")
    for r in results:
        title = r.entry.name or f"Charity {r.entry.charity_number}"
        lines.append(f"### {title} ({r.entry.charity_number})")
        lines.append("")
        if r.success:
            lines.append("- Status: **ok**")
            if r.org_id:
                lines.append(f"- org_id: `{r.org_id}`")
            lines.append(f"- Markdown length: {r.markdown_length} chars")
            if r.themes:
                lines.append(f"- Themes: {', '.join(r.themes)}")
            if r.flagged_themes:
                flagged_strs = [
                    f"{f.get('theme')} ({f.get('confidence', 0):.2f})"
                    for f in r.flagged_themes
                ]
                lines.append(f"- Flagged for review: {', '.join(flagged_strs)}")
            lines.append(
                f"- Usage: {r.usage.input_tokens} input, {r.usage.output_tokens} output"
            )
        else:
            lines.append("- Status: **failed**")
            lines.append(f"- Error: {r.error or 'unknown'}")
        if r.entry.notes:
            lines.append(f"- Notes: {r.entry.notes}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "CharityResult",
    "CorpusEntry",
    "InvalidCorpusError",
    "load_corpus",
    "render_report",
    "run_corpus",
]
