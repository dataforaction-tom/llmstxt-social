"""Tests for the Phase-1 real-world testing harness.

The harness reads a YAML corpus of charity numbers, runs each through the
profile generator, collects per-charity results, and renders a markdown report
the operator can review before iterating to schema v0.2.

Tests mock the generator end-to-end — no CC API, no Anthropic. The CLI
subcommand wires the real generator in production.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from llmstxt_core.llm import Usage
from llmstxt_core.open_org.generator import (
    GenerationResult,
    ProfileGenerationError,
)
from llmstxt_core.open_org.harness import (
    CharityResult,
    CorpusEntry,
    InvalidCorpusError,
    load_corpus,
    render_report,
    run_corpus,
)


# --- load_corpus -----------------------------------------------------------


def test_load_corpus_parses_charity_numbers(tmp_path: Path):
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text(
        "charities:\n"
        "  - charity_number: '1234567'\n"
        "    name: Riverside Community Trust\n"
        "    notes: phase 1 reference profile\n"
        "  - charity_number: '7654321'\n"
    )

    entries = load_corpus(corpus_file)
    assert len(entries) == 2
    assert entries[0].charity_number == "1234567"
    assert entries[0].name == "Riverside Community Trust"
    assert entries[0].notes == "phase 1 reference profile"
    assert entries[1].charity_number == "7654321"
    assert entries[1].name is None
    assert entries[1].notes is None


def test_load_corpus_returns_empty_list_for_empty_corpus(tmp_path: Path):
    """An empty corpus is valid; harness just produces an empty report."""
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text("charities: []\n")
    assert load_corpus(corpus_file) == []


def test_load_corpus_tolerates_missing_charities_key(tmp_path: Path):
    """A file with only comments parses as an empty corpus rather than 500ing."""
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text("# real-world corpus\n# add entries below\n")
    assert load_corpus(corpus_file) == []


def test_load_corpus_rejects_missing_charity_number(tmp_path: Path):
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text("charities:\n  - name: Mystery Org\n")
    with pytest.raises(InvalidCorpusError, match="charity_number"):
        load_corpus(corpus_file)


def test_load_corpus_rejects_malformed_charity_number(tmp_path: Path):
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text("charities:\n  - charity_number: 'ABC'\n")
    with pytest.raises(InvalidCorpusError, match="charity_number"):
        load_corpus(corpus_file)


# --- run_corpus ------------------------------------------------------------


def _fake_result(*, themes: list[str] | None = None, flagged: list[dict] | None = None):
    return GenerationResult(
        org_id="GB-CHC-1234567",
        markdown="---\nschema_version: open-org/v0.1\n---\n\n## Mission\n\nx\n",
        json_payload={"schema_version": "open-org/v0.1", "identity": {"name": "X"}},
        flagged_themes=flagged or [],
        total_usage=Usage(
            input_tokens=120,
            output_tokens=30,
            model="claude-sonnet-4-20250514",
        ),
    )


async def test_run_corpus_records_one_result_per_entry():
    entries = [
        CorpusEntry(charity_number="1234567"),
        CorpusEntry(charity_number="7654321"),
    ]
    fake = mock.AsyncMock(side_effect=[_fake_result(), _fake_result()])

    results = await run_corpus(
        entries,
        anthropic_client=mock.MagicMock(),
        cc_api_key=None,
        generator=fake,
    )

    assert len(results) == 2
    assert all(r.success for r in results)
    assert fake.await_count == 2


async def test_run_corpus_captures_generator_error_as_failed_result():
    """One bad charity must not kill the whole batch."""
    entries = [
        CorpusEntry(charity_number="1234567"),
        CorpusEntry(charity_number="9999999"),
    ]

    async def fake_generator(number, *, anthropic_client, cc_api_key):
        if number == "9999999":
            raise ProfileGenerationError("not found in CC")
        return _fake_result()

    results = await run_corpus(
        entries,
        anthropic_client=mock.MagicMock(),
        cc_api_key=None,
        generator=fake_generator,
    )

    assert results[0].success is True
    assert results[1].success is False
    assert "not found" in results[1].error.lower()


async def test_run_corpus_aggregates_usage_per_result():
    entry = CorpusEntry(charity_number="1234567")
    fake = mock.AsyncMock(return_value=_fake_result())

    results = await run_corpus(
        [entry],
        anthropic_client=mock.MagicMock(),
        cc_api_key=None,
        generator=fake,
    )
    assert results[0].usage.input_tokens == 120
    assert results[0].usage.output_tokens == 30


async def test_run_corpus_records_flagged_themes():
    entry = CorpusEntry(charity_number="1234567")
    fake = mock.AsyncMock(
        return_value=_fake_result(
            flagged=[{"theme": "health", "confidence": 0.55, "reason": "marginal"}]
        )
    )

    results = await run_corpus(
        [entry],
        anthropic_client=mock.MagicMock(),
        cc_api_key=None,
        generator=fake,
    )
    assert results[0].flagged_themes == [
        {"theme": "health", "confidence": 0.55, "reason": "marginal"}
    ]


async def test_run_corpus_with_empty_corpus_returns_empty_list():
    results = await run_corpus(
        [],
        anthropic_client=mock.MagicMock(),
        cc_api_key=None,
        generator=mock.AsyncMock(),
    )
    assert results == []


# --- render_report ---------------------------------------------------------


def _success(charity_number="1234567", name=None, themes=None, flagged=None):
    return CharityResult(
        entry=CorpusEntry(charity_number=charity_number, name=name),
        success=True,
        org_id=f"GB-CHC-{charity_number}",
        markdown_length=512,
        themes=themes or ["education"],
        flagged_themes=flagged or [],
        usage=Usage(input_tokens=100, output_tokens=20),
        error=None,
    )


def _failure(charity_number="1234567", error_message="not found"):
    return CharityResult(
        entry=CorpusEntry(charity_number=charity_number),
        success=False,
        org_id=None,
        markdown_length=0,
        themes=[],
        flagged_themes=[],
        usage=Usage(),
        error=error_message,
    )


def test_render_report_includes_summary_counts():
    results = [_success(), _success(charity_number="2222222"), _failure(charity_number="3")]
    md = render_report(results, run_at=datetime(2026, 5, 11, 14, 30))

    assert "# Real-world corpus run" in md
    assert "2026-05-11" in md
    assert "3 charities" in md
    assert "2 succeeded" in md
    assert "1 failed" in md


def test_render_report_lists_each_charity_with_status():
    results = [_success(charity_number="1234567", name="Acme Aid")]
    md = render_report(results, run_at=datetime(2026, 5, 11))
    assert "Acme Aid" in md
    assert "1234567" in md
    assert "ok" in md.lower() or "succeeded" in md.lower()


def test_render_report_calls_out_flagged_themes():
    results = [
        _success(
            flagged=[{"theme": "health", "confidence": 0.55, "reason": "marginal"}]
        ),
    ]
    md = render_report(results, run_at=datetime(2026, 5, 11))
    assert "health" in md
    assert "0.55" in md


def test_render_report_handles_failure_with_error_message():
    results = [_failure(charity_number="9999999", error_message="CC API 500")]
    md = render_report(results, run_at=datetime(2026, 5, 11))
    assert "9999999" in md
    assert "CC API 500" in md


def test_render_report_handles_empty_results():
    md = render_report([], run_at=datetime(2026, 5, 11))
    assert "0 charities" in md
    # Must not error; empty is a valid report.


def test_render_report_includes_total_usage():
    results = [_success(), _success(charity_number="2")]
    md = render_report(results, run_at=datetime(2026, 5, 11))
    # 2 successes × 100 input + 20 output each.
    assert "200" in md
    assert "40" in md
