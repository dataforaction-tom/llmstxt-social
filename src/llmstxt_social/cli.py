"""Command-line interface for llmstxt-social."""

import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from . import __version__
from .crawler import crawl_site
from .extractor import extract_content, find_charity_number
from .analyzer import analyze_organisation
from .generator import generate_llmstxt
from .validator import validate_llmstxt, ValidationLevel
from .enrichers.charity_commission import find_charity_number as find_charity_num

app = typer.Typer(
    name="llmstxt",
    help="Generate llms.txt files for social sector organisations",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"llmstxt-social version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    ),
):
    """llmstxt-social: Generate llms.txt files for UK social sector organisations."""
    pass


@app.command()
def generate(
    url: str = typer.Argument(..., help="Website URL to process"),
    output: Path = typer.Option(
        Path("./llms.txt"),
        "-o",
        "--output",
        help="Output file path"
    ),
    template: str = typer.Option(
        "charity",
        "-t",
        "--template",
        help="Template: charity or funder"
    ),
    model: str = typer.Option(
        "claude-sonnet-4-20250514",
        "-m",
        "--model",
        help="Claude model to use"
    ),
    max_pages: int = typer.Option(
        30,
        "--max-pages",
        help="Maximum pages to crawl"
    ),
    enrich: bool = typer.Option(
        False,
        "--enrich/--no-enrich",
        help="Fetch Charity Commission data"
    ),
    charity_number: str = typer.Option(
        None,
        "--charity",
        help="Specify charity number directly"
    ),
):
    """Generate an llms.txt file for a website."""

    # Validate template
    if template not in ["charity", "funder"]:
        console.print("[red]Error:[/red] Template must be 'charity' or 'funder'")
        raise typer.Exit(1)

    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    console.print(Panel.fit(
        f"[bold]Generating llms.txt for:[/bold] {url}\n"
        f"[dim]Template: {template} | Model: {model}[/dim]",
        border_style="blue"
    ))

    try:
        # Run the async generation
        result = asyncio.run(_generate_async(
            url=url,
            output=output,
            template=template,
            model=model,
            max_pages=max_pages,
            enrich=enrich,
            charity_number=charity_number
        ))

        if result:
            console.print(f"\n[green]✓[/green] Successfully generated llms.txt")
            console.print(f"[dim]→[/dim] Saved to: {output.absolute()}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


async def _generate_async(
    url: str,
    output: Path,
    template: str,
    model: str,
    max_pages: int,
    enrich: bool,
    charity_number: str | None
) -> bool:
    """Async generation logic."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:

        # Step 1: Crawl website
        crawl_task = progress.add_task(
            f"[cyan]Crawling {url}...",
            total=None
        )

        crawl_result = await crawl_site(
            url=url,
            max_pages=max_pages
        )

        progress.update(
            crawl_task,
            description=f"[green]✓ Crawled {len(crawl_result.pages)} pages"
        )
        progress.stop_task(crawl_task)

        if not crawl_result.pages:
            console.print("[red]Error:[/red] No pages could be crawled")
            return False

        # Show crawl summary
        console.print(f"\n[dim]Found {len(crawl_result.sitemap_urls)} sitemap URLs[/dim]")
        console.print(f"[dim]Fetched {len(crawl_result.pages)} pages[/dim]")

        # Step 2: Extract content
        extract_task = progress.add_task(
            "[cyan]Extracting content...",
            total=len(crawl_result.pages)
        )

        extracted_pages = []
        for page in crawl_result.pages:
            extracted = extract_content(page)
            extracted_pages.append(extracted)
            progress.advance(extract_task)

        progress.update(
            extract_task,
            description=f"[green]✓ Extracted {len(extracted_pages)} pages"
        )

        # Show page type distribution
        page_types = {}
        for page in extracted_pages:
            pt = page.page_type.value
            page_types[pt] = page_types.get(pt, 0) + 1

        console.print("\n[dim]Page types:[/dim]")
        for pt, count in sorted(page_types.items(), key=lambda x: -x[1])[:5]:
            console.print(f"  [dim]{pt}: {count}[/dim]")

        # Step 3: Find charity number if needed
        if enrich and not charity_number:
            console.print("\n[cyan]Looking for charity number...[/cyan]")
            charity_number = find_charity_num(extracted_pages)
            if charity_number:
                console.print(f"[green]✓[/green] Found charity number: {charity_number}")
            else:
                console.print("[yellow]![/yellow] Charity number not found")

        # Step 4: Analyze with Claude
        analysis_task = progress.add_task(
            "[cyan]Analyzing with Claude...",
            total=None
        )

        analysis = await analyze_organisation(
            pages=extracted_pages,
            template=template,
            model=model
        )

        progress.update(
            analysis_task,
            description="[green]✓ Analysis complete"
        )

        # Step 5: Generate llms.txt
        gen_task = progress.add_task(
            "[cyan]Generating llms.txt...",
            total=None
        )

        llmstxt_content = generate_llmstxt(
            analysis=analysis,
            pages=extracted_pages,
            template=template
        )

        progress.update(
            gen_task,
            description="[green]✓ Generated llms.txt"
        )

        # Step 6: Validate
        val_task = progress.add_task(
            "[cyan]Validating...",
            total=None
        )

        validation = validate_llmstxt(
            content=llmstxt_content,
            template=template
        )

        progress.update(
            val_task,
            description="[green]✓ Validation complete"
        )

    # Show validation results
    _show_validation_results(validation)

    # Step 7: Write to file
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(llmstxt_content, encoding='utf-8')

    return True


def _show_validation_results(validation):
    """Display validation results."""
    console.print()

    # Summary
    if validation.valid:
        console.print("[green]✓ Valid llms.txt file[/green]")
    else:
        console.print("[yellow]⚠ llms.txt has validation issues[/yellow]")

    # Scores
    table = Table(show_header=False, box=None)
    table.add_row("Spec compliance:", f"{validation.spec_compliance:.0%}")
    table.add_row("Completeness:", f"{validation.completeness:.0%}")
    if validation.transparency_score:
        table.add_row("Transparency:", validation.transparency_score)

    console.print(table)

    # Issues
    if validation.issues:
        console.print(f"\n[bold]Validation issues ({len(validation.issues)}):[/bold]")

        for issue in validation.issues[:10]:  # Show first 10
            level_color = {
                ValidationLevel.ERROR: "red",
                ValidationLevel.WARNING: "yellow",
                ValidationLevel.INFO: "blue"
            }[issue.level]

            level_symbol = {
                ValidationLevel.ERROR: "✗",
                ValidationLevel.WARNING: "⚠",
                ValidationLevel.INFO: "ℹ"
            }[issue.level]

            line_info = f" (line {issue.line})" if issue.line else ""
            console.print(f"  [{level_color}]{level_symbol}[/{level_color}] {issue.message}{line_info}")

        if len(validation.issues) > 10:
            console.print(f"  [dim]... and {len(validation.issues) - 10} more[/dim]")


@app.command()
def validate(
    path: str = typer.Argument(..., help="Path or URL to llms.txt file"),
    template: str = typer.Option(
        "charity",
        "-t",
        "--template",
        help="Template to validate against: charity or funder"
    ),
):
    """Validate an llms.txt file against the spec."""

    # Validate template
    if template not in ["charity", "funder"]:
        console.print("[red]Error:[/red] Template must be 'charity' or 'funder'")
        raise typer.Exit(1)

    try:
        # Load content
        if path.startswith(('http://', 'https://')):
            # Fetch from URL
            import httpx
            response = httpx.get(path, timeout=10)
            response.raise_for_status()
            content = response.text
            console.print(f"[dim]Fetched from {path}[/dim]\n")
        else:
            # Load from file
            file_path = Path(path)
            if not file_path.exists():
                console.print(f"[red]Error:[/red] File not found: {path}")
                raise typer.Exit(1)

            content = file_path.read_text(encoding='utf-8')
            console.print(f"[dim]Loaded from {file_path.absolute()}[/dim]\n")

        # Validate
        validation = validate_llmstxt(content, template)

        # Show results
        _show_validation_results(validation)

        # Exit code based on validity
        if not validation.valid:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def preview(
    url: str = typer.Argument(..., help="Website URL to preview"),
    max_pages: int = typer.Option(
        30,
        "--max-pages",
        help="Maximum pages to crawl"
    ),
):
    """Preview what would be crawled (dry run)."""

    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    console.print(f"[cyan]Previewing crawl of:[/cyan] {url}\n")

    try:
        # Run crawl
        result = asyncio.run(crawl_site(url=url, max_pages=max_pages))

        # Show results
        console.print(f"[green]✓[/green] Found {len(result.pages)} pages\n")

        if result.robots_txt:
            console.print("[green]✓[/green] robots.txt found")

        if result.sitemap_urls:
            console.print(f"[green]✓[/green] Sitemap found ({len(result.sitemap_urls)} URLs)")

        # Show page list
        console.print(f"\n[bold]Pages that would be crawled:[/bold]\n")

        for idx, page in enumerate(result.pages, 1):
            status_color = "green" if page.status_code == 200 else "yellow"
            console.print(f"  {idx:2d}. [{status_color}]{page.status_code}[/{status_color}] {page.title[:60]}")
            console.print(f"      [dim]{page.url}[/dim]")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def test_api_key():
    """Test if the Anthropic API key is configured correctly."""
    import os
    from anthropic import Anthropic
    from dotenv import load_dotenv
    
    load_dotenv()
    
    console.print(Panel.fit(
        "[bold]Testing Anthropic API Key[/bold]",
        border_style="blue"
    ))
    console.print()
    
    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        console.print("[red]❌ ERROR:[/red] ANTHROPIC_API_KEY not found in environment")
        console.print("\n[bold]Please:[/bold]")
        console.print("1. Create a .env file in the project root")
        console.print("2. Add: [cyan]ANTHROPIC_API_KEY=sk-ant-your-key-here[/cyan]")
        console.print("3. Get your API key from: [link]https://console.anthropic.com[/link]")
        raise typer.Exit(1)
    
    # Check for common issues
    api_key_stripped = api_key.strip()
    if api_key != api_key_stripped:
        console.print("[yellow]⚠️  WARNING:[/yellow] API key has leading/trailing whitespace")
        api_key = api_key_stripped
    
    if not api_key.startswith("sk-ant-"):
        console.print("[yellow]⚠️  WARNING:[/yellow] API key doesn't start with 'sk-ant-'")
        console.print(f"   Starts with: [dim]{api_key[:10]}...[/dim]")
    
    console.print(f"[green]✓[/green] API key found (length: {len(api_key)} characters)")
    console.print(f"   First 10 chars: [dim]{api_key[:10]}...[/dim]")
    console.print()
    
    # Test API call
    try:
        console.print("[cyan]Making test API call...[/cyan]")
        client = Anthropic(api_key=api_key)
        
        # Make a minimal API call
        message = client.messages.create(
            model="claude-3-haiku-20240307",  # Use cheapest model for testing
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'test'"
                }
            ]
        )
        
        response = message.content[0].text
        console.print(f"[green]✓ API call successful![/green]")
        console.print(f"   Response: [dim]{response}[/dim]")
        console.print()
        console.print("[bold green]✅ Your API key is valid and working![/bold green]")
        
    except Exception as e:
        error_str = str(e)
        console.print(f"\n[red]❌ API call failed![/red]")
        console.print(f"   Error: [red]{error_str}[/red]")
        
        if "401" in error_str or "authentication" in error_str.lower():
            console.print("\n[bold]🔍 Authentication Error - Possible issues:[/bold]")
            console.print("   1. API key is incorrect or expired")
            console.print("   2. API key has extra characters or whitespace")
            console.print("   3. API key doesn't have proper permissions")
            console.print("\n[bold]💡 Try:[/bold]")
            console.print("   1. Get a new API key from [link]https://console.anthropic.com[/link]")
            console.print("   2. Make sure your .env file has: [cyan]ANTHROPIC_API_KEY=sk-ant-...[/cyan]")
            console.print("   3. Check there are no quotes around the key in .env")
            console.print("   4. Restart your terminal/IDE after updating .env")
        elif "429" in error_str:
            console.print("\n[yellow]⚠️  Rate limit error - API key is valid but you've hit rate limits[/yellow]")
        else:
            console.print(f"\n   Full error details: [red]{e}[/red]")
        
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
