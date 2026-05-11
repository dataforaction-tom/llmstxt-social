"""Open Org subcommands for the llmstxt CLI.

Phase 1 ships ``llmstxt openorg test-corpus`` for the real-world testing
harness (Step 11). Future subcommands (publish, regenerate, etc.) land here.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.harness import (
    InvalidCorpusError,
    load_corpus,
    render_report,
    run_corpus,
)


openorg_app = typer.Typer(
    name="openorg",
    help="Open Org operations (Phase 1)",
    add_completion=False,
)
console = Console()


@openorg_app.command("test-corpus")
def test_corpus(
    corpus: Path = typer.Option(
        Path("tests/fixtures/real_world_corpus.yaml"),
        "--corpus",
        "-c",
        help="YAML corpus of charities to run.",
    ),
    output_dir: Path = typer.Option(
        Path("tests/reports"),
        "--output",
        "-o",
        help="Directory to write the run report into.",
    ),
):
    """Run the profile generator across the corpus and write a markdown report.

    Hits the real Charity Commission and Anthropic APIs. Operator-driven —
    not part of CI. Use ``ANTHROPIC_API_KEY`` (required) and
    ``CHARITY_COMMISSION_API_KEY`` (optional; falls back to the public
    register scraper) from the environment.
    """
    if not corpus.exists():
        console.print(f"[red]Corpus file not found:[/red] {corpus}")
        raise typer.Exit(code=1)

    try:
        entries = load_corpus(corpus)
    except InvalidCorpusError as exc:
        console.print(f"[red]Invalid corpus:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not entries:
        console.print(
            "[yellow]Corpus is empty.[/yellow] Add charity numbers to "
            f"{corpus} before running."
        )
        # Still write an empty report so the harness output is observable.

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        console.print("[red]ANTHROPIC_API_KEY not set in environment.[/red]")
        raise typer.Exit(code=1)
    cc_api_key = os.getenv("CHARITY_COMMISSION_API_KEY") or None

    client = CachedAnthropic(api_key=anthropic_key)
    console.print(f"Running {len(entries)} charit{'y' if len(entries) == 1 else 'ies'}…")

    results = asyncio.run(
        run_corpus(
            entries,
            anthropic_client=client,
            cc_api_key=cc_api_key,
        )
    )

    run_at = datetime.utcnow()
    report = render_report(results, run_at=run_at)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = run_at.strftime("%Y%m%d-%H%M%S")
    report_path = output_dir / f"real_world_run_{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded
    console.print(
        f"[green]Run complete:[/green] {succeeded} ok, {failed} failed."
    )
    console.print(f"Report written to [cyan]{report_path}[/cyan]")


__all__ = ["openorg_app"]
