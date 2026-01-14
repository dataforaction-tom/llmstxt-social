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
from llmstxt_core.crawler import crawl_site
from llmstxt_core.extractor import extract_content, find_charity_number
from llmstxt_core.analyzer import analyze_organisation
from llmstxt_core.generator import generate_llmstxt
from llmstxt_core.validator import validate_llmstxt, ValidationLevel
from llmstxt_core.enrichers.charity_commission import find_charity_number as find_charity_num, fetch_charity_data
from llmstxt_core.enrichers.threesixty_giving import fetch_360giving_data

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
        help="Template: charity, funder, public_sector, or startup"
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
        True,
        "--enrich/--no-enrich",
        help="Fetch Charity Commission data (default: enabled)"
    ),
    enrich_360: bool = typer.Option(
        False,
        "--enrich-360/--no-enrich-360",
        help="Fetch 360Giving data for funders"
    ),
    use_playwright: bool = typer.Option(
        False,
        "--playwright/--no-playwright",
        help="Use Playwright for JavaScript-rendered sites"
    ),
    charity_number: str = typer.Option(
        None,
        "--charity",
        help="Specify charity number directly"
    ),
):
    """Generate an llms.txt file for a website."""

    # Validate template
    if template not in ["charity", "funder", "public_sector", "startup"]:
        console.print("[red]Error:[/red] Template must be 'charity', 'funder', 'public_sector', or 'startup'")
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
            enrich_360=enrich_360,
            use_playwright=use_playwright,
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
    enrich_360: bool,
    use_playwright: bool,
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

        # Choose crawler based on flag
        if use_playwright:
            console.print("[dim]Using Playwright for JavaScript rendering...[/dim]")
            from llmstxt_core.crawler_playwright import crawl_site_with_playwright
            crawl_result = await crawl_site_with_playwright(
                url=url,
                max_pages=max_pages
            )
        else:
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
        charity_data = None
        grant_data = None

        if enrich and not charity_number and template == "charity":
            console.print("\n[cyan]Looking for charity number...[/cyan]")
            charity_number = find_charity_num(extracted_pages)
            if charity_number:
                console.print(f"[green]✓[/green] Found charity number: {charity_number}")
            else:
                console.print("[yellow]![/yellow] Charity number not found on website")
                console.print("\n[dim]Charity numbers are usually 6-7 digits (e.g., 1094112)[/dim]")

                # Prompt user for charity number
                user_input = typer.prompt(
                    "\nEnter charity number (or press Enter to skip enrichment)",
                    default="",
                    show_default=False
                )

                if user_input.strip():
                    # Validate it's a number and correct length
                    cleaned = user_input.strip().replace(" ", "")
                    if cleaned.isdigit() and 6 <= len(cleaned) <= 7:
                        charity_number = cleaned
                        console.print(f"[green]✓[/green] Using charity number: {charity_number}")
                    else:
                        console.print("[red]✗[/red] Invalid charity number format (must be 6-7 digits)")
                        console.print("[yellow]Continuing without enrichment...[/yellow]")
                else:
                    console.print("[dim]Skipping charity enrichment[/dim]")

        # Step 3a: Enrich with Charity Commission data
        if enrich and charity_number and template == "charity":
            import os
            console.print("\n[cyan]Fetching Charity Commission data...[/cyan]")

            cc_api_key = os.getenv("CHARITY_COMMISSION_API_KEY")
            charity_data = await fetch_charity_data(charity_number, cc_api_key)

            if charity_data:
                console.print(f"[green]✓[/green] Enriched with official charity data")
                console.print(f"  [dim]Name: {charity_data.name}[/dim]")
                if charity_data.latest_income:
                    console.print(f"  [dim]Income: £{charity_data.latest_income:,}[/dim]")
            else:
                console.print("[yellow]![/yellow] Could not fetch Charity Commission data")

        # Step 3b: Enrich with 360Giving data (for funders)
        if enrich_360 and template == "funder":
            console.print("\n[cyan]Fetching 360Giving grants data...[/cyan]")

            # Get the funder name from first page title or analysis
            funder_name = extracted_pages[0].title if extracted_pages else None

            if funder_name:
                grant_data = await fetch_360giving_data(funder_name, charity_number)

                if grant_data:
                    console.print(f"[green]✓[/green] Found 360Giving data")
                    console.print(f"  [dim]Total grants: {grant_data.total_grants}[/dim]")
                    console.print(f"  [dim]Average grant: £{grant_data.average_grant:,.0f}[/dim]")
                else:
                    console.print("[yellow]![/yellow] No 360Giving data found")

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
            template=template,
            charity_data=charity_data,
            grant_data=grant_data
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


@app.command()
def assess(
    source: str = typer.Argument(..., help="URL of website or path to llms.txt file to assess"),
    template: str = typer.Option(
        None,
        "-t",
        "--template",
        help="Template type (auto-detected if not specified)"
    ),
    output: Path = typer.Option(
        None,
        "-o",
        "--output",
        help="Output file path (default: assessment-{timestamp})"
    ),
    format: str = typer.Option(
        "both",
        "-f",
        "--format",
        help="Output format: json, markdown, or both"
    ),
    deep_analysis: bool = typer.Option(
        True,
        "--deep/--quick",
        help="Use Claude for quality analysis (default: enabled)"
    ),
    enrich: bool = typer.Option(
        True,
        "--enrich/--no-enrich",
        help="Fetch enrichment data for context (default: enabled)"
    ),
):
    """Assess quality and completeness of an llms.txt file."""

    # Determine if source is URL or file path
    is_url = source.startswith(('http://', 'https://')) or (not Path(source).exists() and '.' in source and not source.endswith('.txt'))

    console.print(Panel.fit(
        f"[bold]Assessing:[/bold] {source}\n"
        f"[dim]Format: {format} | Deep analysis: {deep_analysis}[/dim]",
        border_style="cyan"
    ))

    try:
        if is_url:
            # Website assessment path
            asyncio.run(_assess_from_website(
                url=source,
                template=template,
                output=output,
                format=format,
                deep_analysis=deep_analysis,
                enrich=enrich
            ))
        else:
            # File assessment path
            asyncio.run(_assess_from_file(
                file_path=source,
                template=template,
                output=output,
                format=format,
                deep_analysis=deep_analysis,
                enrich=enrich
            ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


async def _assess_from_website(
    url: str,
    template: str | None,
    output: Path | None,
    format: str,
    deep_analysis: bool,
    enrich: bool
):
    """Assess by generating llms.txt from website then analyzing it."""
    from datetime import datetime
    from llmstxt_core.assessor import LLMSTxtAssessor
    from anthropic import Anthropic
    import os

    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:

        # 1. Crawl website
        crawl_task = progress.add_task("Crawling website...", total=None)
        crawl_result = await crawl_site(url, max_pages=30)
        progress.update(crawl_task, description="[green]✓[/green] Crawled website", completed=True)

        # 2. Extract content
        extract_task = progress.add_task("Extracting content...", total=None)
        extracted_pages = [extract_content(p) for p in crawl_result.pages]
        progress.update(extract_task, description="[green]✓[/green] Extracted content", completed=True)

        # 3. Auto-detect template if not specified
        if not template:
            template = _detect_template_type(extracted_pages)
            console.print(f"[dim]Auto-detected template: {template}[/dim]")

        # 4. Get enrichment data
        charity_data = None
        if enrich and template == "charity":
            enrich_task = progress.add_task("Fetching Charity Commission data...", total=None)
            charity_number = find_charity_num(extracted_pages)
            if charity_number:
                charity_data = await fetch_charity_data(charity_number)
                if charity_data:
                    progress.update(enrich_task, description="[green]✓[/green] Fetched enrichment data", completed=True)
                else:
                    progress.update(enrich_task, description="[yellow]○[/yellow] No enrichment data found", completed=True)
            else:
                progress.update(enrich_task, description="[yellow]○[/yellow] No charity number found", completed=True)

        # 5. Analyze with Claude
        analysis_task = progress.add_task("Analyzing organization...", total=None)
        analysis = await analyze_organisation(extracted_pages, template)
        progress.update(analysis_task, description="[green]✓[/green] Analyzed organization", completed=True)

        # 6. Generate llms.txt
        gen_task = progress.add_task("Generating llms.txt...", total=None)
        llmstxt_content = generate_llmstxt(analysis, extracted_pages, template, charity_data)
        progress.update(gen_task, description="[green]✓[/green] Generated llms.txt", completed=True)

        # 7. Assess the generated llms.txt
        assess_task = progress.add_task("Assessing quality...", total=None)

        client = None
        if deep_analysis:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                client = Anthropic(api_key=api_key)
            else:
                console.print("[yellow]Warning: No API key found, skipping AI quality analysis[/yellow]")

        assessor = LLMSTxtAssessor(template, client)

        assessment_result = await assessor.assess(
            llmstxt_content=llmstxt_content,
            website_url=url,
            crawl_result=crawl_result,
            enrichment_data=charity_data
        )

        progress.update(assess_task, description="[green]✓[/green] Assessment complete", completed=True)

    # 8. Output results
    _output_assessment(assessment_result, output, format, llmstxt_content, url)
    _show_assessment_summary(assessment_result)


async def _assess_from_file(
    file_path: str,
    template: str | None,
    output: Path | None,
    format: str,
    deep_analysis: bool,
    enrich: bool
):
    """Assess an existing llms.txt file."""
    from datetime import datetime
    from llmstxt_core.assessor import LLMSTxtAssessor
    from anthropic import Anthropic
    import os

    # 1. Load file
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    llmstxt_content = path.read_text(encoding='utf-8')

    # 2. Auto-detect template from content
    if not template:
        template = _detect_template_from_content(llmstxt_content)
        console.print(f"[dim]Auto-detected template: {template}[/dim]")

    # 3. Try to extract website URL from content for enrichment
    website_url = _extract_url_from_llmstxt(llmstxt_content)

    crawl_result = None
    charity_data = None

    if website_url and enrich:
        console.print(f"[cyan]Found website URL: {website_url}[/cyan]")

        # Ask if user wants to crawl for gap analysis
        if typer.confirm("Crawl website for gap analysis?", default=True):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                crawl_task = progress.add_task("Crawling website...", total=None)
                crawl_result = await crawl_site(website_url, max_pages=30)
                progress.update(crawl_task, description="[green]✓[/green] Crawled website", completed=True)

                # Get enrichment data if charity
                if template == "charity":
                    from llmstxt_core.extractor import extract_content
                    enrich_task = progress.add_task("Fetching enrichment data...", total=None)
                    extracted_pages = [extract_content(p) for p in crawl_result.pages]
                    charity_number = find_charity_num(extracted_pages)
                    if charity_number:
                        charity_data = await fetch_charity_data(charity_number)
                    progress.update(enrich_task, description="[green]✓[/green] Fetched enrichment data", completed=True)

    # 4. Assess
    console.print("[cyan]Running assessment...[/cyan]")

    client = None
    if deep_analysis:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            client = Anthropic(api_key=api_key)
        else:
            console.print("[yellow]Warning: No API key found, skipping AI quality analysis[/yellow]")

    assessor = LLMSTxtAssessor(template, client)

    assessment_result = await assessor.assess(
        llmstxt_content=llmstxt_content,
        website_url=website_url,
        crawl_result=crawl_result,
        enrichment_data=charity_data
    )

    # 5. Output
    _output_assessment(assessment_result, output, format, llmstxt_content, website_url)
    _show_assessment_summary(assessment_result)


def _detect_template_type(extracted_pages) -> str:
    """Auto-detect template type from extracted pages."""
    from llmstxt_core.extractor import PageType

    page_types = set(p.page_type for p in extracted_pages)

    # Check for funder-specific page types
    if PageType.FUNDING_PRIORITIES in page_types or PageType.HOW_TO_APPLY in page_types or PageType.PAST_GRANTS in page_types:
        return "funder"

    # Check for startup-specific page types
    if PageType.PRICING in page_types or PageType.INVESTORS in page_types:
        return "startup"

    # Check for public sector indicators in titles/content
    for page in extracted_pages:
        title_lower = page.title.lower()
        if any(term in title_lower for term in ["council", "nhs", "government", "local authority"]):
            return "public_sector"

    # Default to charity
    return "charity"


def _detect_template_from_content(content: str) -> str:
    """Auto-detect template type from llms.txt content."""
    content_lower = content.lower()

    # Check for template-specific sections
    if "what we fund" in content_lower or "for applicants" in content_lower:
        return "funder"
    elif "for investors" in content_lower or ("pricing" in content_lower and "product" in content_lower):
        return "startup"
    elif "for service users" in content_lower or ("council" in content_lower or "nhs" in content_lower):
        return "public_sector"
    else:
        return "charity"


def _extract_url_from_llmstxt(content: str) -> str | None:
    """Extract website URL from llms.txt content."""
    import re

    # Look for URLs in markdown links
    url_pattern = r'\[.*?\]\((https?://[^\)]+)\)'
    matches = re.findall(url_pattern, content)

    if matches:
        # Return the domain of the first URL
        from urllib.parse import urlparse
        parsed = urlparse(matches[0])
        return f"{parsed.scheme}://{parsed.netloc}"

    return None


def _output_assessment(assessment_result, output: Path | None, format: str, llmstxt_content: str, website_url: str | None):
    """Generate output files."""
    from datetime import datetime
    import json

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if output is None:
        base_name = f"assessment-{timestamp}"
    else:
        base_name = output.stem

    # JSON output
    if format in ["json", "both"]:
        json_path = Path(f"{base_name}.json") if output is None else output.with_suffix('.json')

        data = {
            "template_type": assessment_result.template_type,
            "timestamp": datetime.now().isoformat(),
            "website_url": website_url,
            "scores": {
                "overall": assessment_result.overall_score,
                "completeness": assessment_result.completeness_score,
                "quality": assessment_result.quality_score,
                **assessment_result.scores
            },
            "sections": [
                {
                    "name": s.section_name,
                    "present": s.present,
                    "content_quality": s.content_quality,
                    "completeness": s.completeness
                }
                for s in assessment_result.section_assessments
            ],
            "findings": [
                {
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "message": f.message,
                    "section": f.section,
                    "suggestion": f.suggestion
                }
                for f in assessment_result.findings
            ],
            "website_gaps": {
                "missing_page_types": assessment_result.website_gaps.missing_page_types,
                "sitemap_detected": assessment_result.website_gaps.sitemap_detected,
                "suggested_pages": assessment_result.website_gaps.suggested_pages
            } if assessment_result.website_gaps else None,
            "org_size": {
                "category": assessment_result.org_size.category,
                "income": assessment_result.org_size.income
            } if assessment_result.org_size else None,
            "recommendations": assessment_result.recommendations
        }

        json_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        console.print(f"[green]✓[/green] JSON saved to: {json_path.absolute()}")

    # Markdown output
    if format in ["markdown", "both"]:
        md_path = Path(f"{base_name}.md") if output is None else output.with_suffix('.md')

        lines = []

        # Header
        lines.append(f"# llms.txt Quality Assessment Report\n")
        lines.append(f"**Template Type**: {assessment_result.template_type}\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        if website_url:
            lines.append(f"**Website**: {website_url}\n")
        lines.append("\n")

        # Scores
        lines.append("## Overall Scores\n")
        lines.append(f"- **Overall**: {assessment_result.overall_score}/100")
        lines.append(f"- **Completeness**: {assessment_result.completeness_score}/100")
        lines.append(f"- **Quality**: {assessment_result.quality_score}/100\n\n")

        # Grade
        if assessment_result.overall_score >= 90:
            grade = "A"
        elif assessment_result.overall_score >= 80:
            grade = "B"
        elif assessment_result.overall_score >= 70:
            grade = "C"
        elif assessment_result.overall_score >= 60:
            grade = "D"
        else:
            grade = "F"
        lines.append(f"**Grade**: {grade}\n\n")

        # Organization size (if charity)
        if assessment_result.org_size:
            lines.append("## Organization Profile\n")
            lines.append(f"- **Size Category**: {assessment_result.org_size.category.capitalize()}")
            if assessment_result.org_size.income:
                lines.append(f"- **Annual Income**: £{assessment_result.org_size.income:,}\n\n")

        # Section breakdown
        lines.append("## Section Assessment\n")
        for section in assessment_result.section_assessments:
            status = "✓" if section.present else "✗"
            lines.append(f"### {status} {section.section_name}")
            if section.present:
                lines.append(f"- Content Quality: {section.content_quality * 100:.0f}%")
                lines.append(f"- Completeness: {section.completeness * 100:.0f}%\n")
            else:
                lines.append("- **Missing** - This section should be added\n")

        # Findings by severity
        lines.append("\n## Findings\n")

        from llmstxt_core.assessor import IssueSeverity
        for severity in [IssueSeverity.CRITICAL, IssueSeverity.MAJOR, IssueSeverity.MINOR]:
            severity_findings = [f for f in assessment_result.findings if f.severity == severity]
            if severity_findings:
                lines.append(f"\n### {severity.value.capitalize()} Issues\n")
                for finding in severity_findings:
                    lines.append(f"- **{finding.section or 'General'}**: {finding.message}")
                    if finding.suggestion:
                        lines.append(f"  - *Suggestion*: {finding.suggestion}")
                    lines.append("")

        # Website gaps
        if assessment_result.website_gaps:
            lines.append("\n## Website Data Gaps\n")
            if assessment_result.website_gaps.missing_page_types:
                lines.append("**Missing Page Types:**\n")
                for pt in assessment_result.website_gaps.missing_page_types:
                    lines.append(f"- {pt}")
                lines.append("")

            if assessment_result.website_gaps.suggested_pages:
                lines.append("**Suggested Improvements:**\n")
                for suggestion in assessment_result.website_gaps.suggested_pages:
                    lines.append(f"- {suggestion}")
                lines.append("")

            lines.append(f"**Sitemap Detected**: {'Yes' if assessment_result.website_gaps.sitemap_detected else 'No'}\n")

        # Recommendations
        lines.append("\n## Recommendations\n")
        for i, rec in enumerate(assessment_result.recommendations, 1):
            lines.append(f"{i}. {rec}")

        # Appendix: Full llms.txt
        lines.append("\n\n---\n\n## Appendix: Full llms.txt Content\n")
        lines.append("```")
        lines.append(llmstxt_content)
        lines.append("```")

        md_path.write_text("\n".join(lines), encoding='utf-8')
        console.print(f"[green]✓[/green] Markdown saved to: {md_path.absolute()}")


def _show_assessment_summary(assessment_result):
    """Display assessment summary in terminal."""

    # Create summary table
    table = Table(title="\nAssessment Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")

    def get_grade_color(score):
        if score >= 90:
            return "green"
        elif score >= 80:
            return "yellow"
        elif score >= 70:
            return "orange"
        else:
            return "red"

    overall_color = get_grade_color(assessment_result.overall_score)
    table.add_row("Overall", f"[{overall_color}]{assessment_result.overall_score:.1f}/100[/{overall_color}]", f"[{overall_color}]{'A' if assessment_result.overall_score >= 90 else 'B' if assessment_result.overall_score >= 80 else 'C' if assessment_result.overall_score >= 70 else 'D'}[/{overall_color}]")

    completeness_color = get_grade_color(assessment_result.completeness_score)
    table.add_row("Completeness", f"[{completeness_color}]{assessment_result.completeness_score:.1f}/100[/{completeness_color}]", "")

    quality_color = get_grade_color(assessment_result.quality_score)
    table.add_row("Quality", f"[{quality_color}]{assessment_result.quality_score:.1f}/100[/{quality_color}]", "")

    console.print(table)

    # Show top recommendations
    if assessment_result.recommendations:
        console.print("\n[bold cyan]Top Recommendations:[/bold cyan]")
        for i, rec in enumerate(assessment_result.recommendations[:3], 1):
            console.print(f"  {i}. {rec}")

    console.print()


if __name__ == "__main__":
    app()
