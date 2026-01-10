# Claude Code Prompt: llmstxt-social MVP

## Project Overview

Build an open source Python CLI tool that generates llms.txt files for UK social sector organisations (charities, VCSE orgs) and funders, following the llmstxt.org specification with sector-specific extensions.

## Repository Setup

Create a new Python project with this structure:

```
llmstxt-social/
├── pyproject.toml          # Project config (use uv/hatch)
├── README.md
├── LICENSE                  # MIT
├── .env.example
├── src/
│   └── llmstxt_social/
│       ├── __init__.py
│       ├── cli.py           # CLI entrypoint (click or typer)
│       ├── crawler.py       # Static site crawler
│       ├── extractor.py     # Content extraction from HTML
│       ├── analyzer.py      # LLM analysis
│       ├── generator.py     # llms.txt generation
│       ├── validator.py     # Spec validation
│       ├── enrichers/
│       │   ├── __init__.py
│       │   └── charity_commission.py
│       └── templates/
│           ├── __init__.py
│           ├── charity.py
│           └── funder.py
├── tests/
│   ├── __init__.py
│   ├── test_crawler.py
│   ├── test_extractor.py
│   └── test_generator.py
└── examples/
    ├── charities/
    └── funders/
```

## Core Dependencies

```toml
[project]
dependencies = [
    "httpx>=0.27",           # Async HTTP client
    "beautifulsoup4>=4.12",  # HTML parsing
    "lxml>=5.0",             # Fast HTML parser
    "anthropic>=0.40",       # Claude API
    "typer>=0.12",           # CLI framework
    "rich>=13.0",            # Pretty terminal output
    "pydantic>=2.0",         # Data validation
    "python-dotenv>=1.0",    # Environment variables
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.5",
]
```

## Module Specifications

### 1. crawler.py

Crawl a website to discover and fetch pages.

```python
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class Page:
    url: str
    title: str
    html: str
    status_code: int

@dataclass 
class CrawlResult:
    base_url: str
    pages: list[Page]
    robots_txt: str | None
    sitemap_urls: list[str]

async def crawl_site(
    url: str,
    max_pages: int = 30,
    timeout: int = 30,
    respect_robots: bool = True
) -> CrawlResult:
    """
    Crawl a website starting from the given URL.
    
    1. Fetch and parse robots.txt
    2. Try to find and parse sitemap.xml
    3. If no sitemap, discover pages by following links from homepage
    4. Fetch each page (respecting robots.txt rules)
    5. Return CrawlResult with all fetched pages
    
    Use httpx.AsyncClient for requests.
    Implement basic rate limiting (1 req/sec).
    Handle common errors gracefully (timeouts, 404s, etc).
    """
    pass
```

Key implementation details:
- Use `httpx.AsyncClient` with reasonable timeouts
- Parse robots.txt using `urllib.robotparser`
- Try common sitemap locations: `/sitemap.xml`, `/sitemap_index.xml`
- For link discovery, only follow internal links
- Breadth-first crawl with depth limit of 2-3
- Skip non-HTML resources (images, PDFs, etc) - but note PDF URLs for later
- Respect `Crawl-delay` if specified in robots.txt

### 2. extractor.py

Extract structured content from HTML pages.

```python
from dataclasses import dataclass
from enum import Enum

class PageType(Enum):
    HOME = "home"
    ABOUT = "about"
    SERVICES = "services"
    CONTACT = "contact"
    GET_HELP = "get_help"
    VOLUNTEER = "volunteer"
    DONATE = "donate"
    NEWS = "news"
    TEAM = "team"
    POLICY = "policy"
    # Funder-specific
    FUNDING_PRIORITIES = "funding_priorities"
    HOW_TO_APPLY = "how_to_apply"
    PAST_GRANTS = "past_grants"
    ELIGIBILITY = "eligibility"
    OTHER = "other"

@dataclass
class ExtractedPage:
    url: str
    title: str
    description: str | None        # meta description
    headings: list[str]            # h1, h2 headings
    body_text: str                 # Main content, cleaned
    page_type: PageType            # Classified type
    contact_info: dict | None      # Extracted email, phone, address
    charity_number: str | None     # If found on page

def extract_content(page: Page) -> ExtractedPage:
    """
    Extract structured content from an HTML page.
    
    1. Parse HTML with BeautifulSoup
    2. Extract title (from <title> or <h1>)
    3. Extract meta description
    4. Extract all headings (h1, h2)
    5. Extract main body text (strip nav, footer, scripts, etc)
    6. Classify page type based on URL patterns and content
    7. Look for contact information (regex for email, phone)
    8. Look for charity registration number patterns
    
    Return ExtractedPage with all structured data.
    """
    pass

def classify_page_type(url: str, title: str, headings: list[str], body_text: str) -> PageType:
    """
    Classify a page into one of our defined types.
    
    Use a combination of:
    - URL patterns (/about, /contact, /services, /apply, etc)
    - Title keywords
    - Heading keywords
    - Body text keywords
    
    Return the most likely PageType.
    """
    pass
```

Key implementation details:
- Use BeautifulSoup with lxml parser
- Strip script, style, nav, header, footer elements before extracting body
- Collapse whitespace in body text
- Regex patterns for UK phone numbers, email addresses
- Regex for charity numbers: `registered charity (\d{6,7})` etc
- Page classification should be rule-based (not LLM) for speed

### 3. analyzer.py

Use Claude to analyze extracted content and generate structured data.

```python
from dataclasses import dataclass
from anthropic import Anthropic

@dataclass
class OrganisationAnalysis:
    name: str
    org_type: str                  # charity, CIC, CIO, etc
    registration_number: str | None
    mission: str                   # One sentence
    description: str               # 2-3 sentences
    geographic_area: str
    services: list[dict]           # [{name, description, eligibility}]
    beneficiaries: str
    themes: list[str]
    contact: dict                  # {email, phone, address, hours}
    team_info: str | None
    ai_guidance: list[str]         # Things AI should know

@dataclass
class FunderAnalysis:
    name: str
    funder_type: str               # independent, corporate, community
    registration_number: str | None
    mission: str
    description: str
    geographic_focus: str
    thematic_focus: list[str]
    programmes: list[dict]         # [{name, description, eligibility}]
    grant_sizes: dict              # {min, max, typical}
    who_can_apply: list[str]
    who_cannot_apply: list[str]
    application_process: str
    deadlines: str | None
    contact: dict
    success_factors: list[str]     # What makes strong applications
    ai_guidance: list[str]

async def analyze_organisation(
    pages: list[ExtractedPage],
    template: str = "charity"      # "charity" or "funder"
) -> OrganisationAnalysis | FunderAnalysis:
    """
    Use Claude to analyze the extracted pages and produce structured data.
    
    1. Prepare a prompt with all page content
    2. Call Claude API with appropriate system prompt
    3. Parse the structured response
    4. Return the appropriate analysis dataclass
    """
    pass
```

System prompts for Claude (include in module):

**Charity Analysis Prompt:**
```
You are analyzing a UK VCSE (voluntary, community, social enterprise) 
organisation's website to create an llms.txt file.

Given the extracted content from their website pages, identify and return 
as JSON:

{
  "name": "Full official name",
  "org_type": "charity|CIC|CIO|unincorporated|social_enterprise|other",
  "registration_number": "Charity/company number if found, else null",
  "mission": "One sentence primary mission",
  "description": "2-3 sentences expanding on mission, who they serve, what makes them distinctive",
  "geographic_area": "Area served (be specific - local authority, region, etc)",
  "services": [
    {"name": "Service name", "description": "What it is", "eligibility": "Who can access"}
  ],
  "beneficiaries": "Who they primarily serve",
  "themes": ["theme1", "theme2"],
  "contact": {"email": "", "phone": "", "address": "", "hours": ""},
  "team_info": "Brief note on team size/structure if mentioned",
  "ai_guidance": [
    "Important things AI systems should know when representing this org",
    "E.g. preferred name, sensitive topics, common misconceptions"
  ]
}

Be concise. Extract only what's clearly stated - don't infer or hallucinate.
If information isn't available, use null.
```

**Funder Analysis Prompt:**
```
You are analyzing a UK funder/foundation's website to create an llms.txt file.

Given the extracted content, identify and return as JSON:

{
  "name": "Full foundation/trust name",
  "funder_type": "independent|corporate|community|family|statutory",
  "registration_number": "Charity number if found",
  "mission": "One sentence on funding mission",
  "description": "2-3 sentences on approach, values, what makes them distinctive",
  "geographic_focus": "Where they fund",
  "thematic_focus": ["theme1", "theme2"],
  "programmes": [
    {"name": "Programme name", "description": "What it funds", "eligibility": "Who can apply"}
  ],
  "grant_sizes": {"min": null, "max": null, "typical": "typical range as string"},
  "who_can_apply": ["Registered charities", "CICs", etc],
  "who_cannot_apply": ["Individuals", "Organisations under 1 year old", etc],
  "application_process": "Brief description of how to apply",
  "deadlines": "Application deadlines if mentioned",
  "contact": {"email": "", "phone": "", "grants_contact": ""},
  "success_factors": [
    "What makes a strong application according to this funder"
  ],
  "ai_guidance": [
    "Important things AI should know - e.g. don't guarantee funding"
  ]
}

Be concise. Extract only what's clearly stated.
```

### 4. generator.py

Generate the llms.txt file from analysis.

```python
def generate_llmstxt(
    analysis: OrganisationAnalysis | FunderAnalysis,
    pages: list[ExtractedPage],
    template: str = "charity"
) -> str:
    """
    Generate llms.txt content following the llmstxt.org spec.
    
    Structure:
    # Name
    > One-line description
    
    Context paragraphs...
    
    ## Section
    - [Page Title](url): Description
    
    ## Optional
    - [Less important pages](url): Description
    
    ## For Funders (charity template) / For Applicants (funder template)
    Structured data section
    
    ## For AI Systems
    Guidance for AI
    """
    pass

def generate_charity_llmstxt(
    analysis: OrganisationAnalysis,
    pages: list[ExtractedPage]
) -> str:
    """Generate llms.txt for a charity/VCSE org."""
    pass

def generate_funder_llmstxt(
    analysis: FunderAnalysis,
    pages: list[ExtractedPage]
) -> str:
    """Generate llms.txt for a funder/foundation."""
    pass
```

Output should follow this structure for charities:
```markdown
# {name}

> {mission}

{org_type}, {registration if available}. {description}

## About

- [About Us]({about_url}): {description}
- [Our Team]({team_url}): {description}

## Services

- [Service Name]({url}): {description}

## Get Help

- [Access Support]({url}): How to access services
- [Contact]({url}): Contact details

## Get Involved

- [Volunteer]({url}): Volunteering opportunities  
- [Donate]({url}): Support our work

## Optional

- [News]({url}): Latest updates
- [Policies]({url}): Organisational policies

## For Funders

- Registration: {registration}
- Founded: {if available}
- Annual income: {if available}
- Geography: {geographic_area}
- Themes: {themes}
- Beneficiaries: {beneficiaries}
- Contact for funders: {email}

## For AI Systems

When representing this organisation:
{ai_guidance as bullet points}
- Always verify current service availability
- Direct urgent enquiries to official channels
```

### 5. validator.py

Validate generated llms.txt against the spec.

```python
from dataclasses import dataclass
from enum import Enum

class ValidationLevel(Enum):
    ERROR = "error"      # Breaks spec
    WARNING = "warning"  # Recommended but not required
    INFO = "info"        # Suggestion

@dataclass
class ValidationIssue:
    level: ValidationLevel
    message: str
    line: int | None = None

@dataclass
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue]
    spec_compliance: float         # 0-1 score
    completeness: float            # 0-1 score for social sector fields
    transparency_score: str | None # For funders: "Basic", "Transparent", "Open"

def validate_llmstxt(
    content: str,
    template: str = "charity"
) -> ValidationResult:
    """
    Validate llms.txt content against the spec.
    
    Checks:
    - Has H1 heading (required)
    - H1 is first element
    - Has blockquote after H1
    - All sections are H2
    - URL list format is correct
    - No broken markdown syntax
    
    Social sector checks:
    - Has recommended sections
    - Has contact information
    - Has For AI Systems section
    
    Funder transparency score:
    - Basic: required fields present
    - Transparent: includes success rate, relationship approach
    - Open: all fields, links to 360Giving
    """
    pass
```

### 6. cli.py

Command-line interface using Typer.

```python
import typer
from rich.console import Console
from rich.progress import Progress

app = typer.Typer(
    name="llmstxt",
    help="Generate llms.txt files for social sector organisations"
)
console = Console()

@app.command()
def generate(
    url: str = typer.Argument(..., help="Website URL to process"),
    output: str = typer.Option("./llms.txt", "-o", "--output", help="Output file path"),
    template: str = typer.Option("charity", "-t", "--template", help="Template: charity or funder"),
    model: str = typer.Option("claude-sonnet-4-20250514", "-m", "--model", help="LLM model to use"),
    max_pages: int = typer.Option(30, "--max-pages", help="Maximum pages to crawl"),
    enrich: bool = typer.Option(True, "--enrich/--no-enrich", help="Fetch Charity Commission data"),
    charity_number: str = typer.Option(None, "--charity", help="Specify charity number directly"),
):
    """Generate an llms.txt file for a website."""
    # Implementation:
    # 1. Show progress with rich
    # 2. Crawl site
    # 3. Extract content
    # 4. Optionally enrich with Charity Commission
    # 5. Analyze with LLM
    # 6. Generate llms.txt
    # 7. Validate
    # 8. Write to output
    # 9. Show summary
    pass

@app.command()
def validate(
    path: str = typer.Argument(..., help="Path or URL to llms.txt file"),
    template: str = typer.Option("charity", "-t", "--template", help="Template to validate against"),
):
    """Validate an llms.txt file against the spec."""
    pass

@app.command()
def preview(
    url: str = typer.Argument(..., help="Website URL to preview"),
    max_pages: int = typer.Option(30, "--max-pages", help="Maximum pages to crawl"),
):
    """Preview what would be crawled (dry run)."""
    pass

if __name__ == "__main__":
    app()
```

### 7. enrichers/charity_commission.py

Fetch data from the Charity Commission API.

```python
from dataclasses import dataclass

@dataclass
class CharityData:
    name: str
    number: str
    status: str
    date_registered: str | None
    date_removed: str | None
    latest_income: int | None
    latest_expenditure: int | None
    charitable_objects: str | None
    activities: str | None
    trustees: list[str]
    contact: dict

async def fetch_charity_data(charity_number: str) -> CharityData | None:
    """
    Fetch charity data from the Charity Commission API.
    
    API: https://api.charitycommission.gov.uk/
    
    Returns None if charity not found.
    """
    pass

def find_charity_number(pages: list[ExtractedPage]) -> str | None:
    """
    Try to find a charity registration number in the extracted pages.
    
    Look for patterns like:
    - "Registered charity 1234567"
    - "Charity no. 1234567"
    - "Charity number: 1234567"
    - In footer, about page, contact page
    """
    pass
```

Note: The Charity Commission API is free but requires registration. For MVP, we can also scrape the public register page as fallback.

## CLI Usage Examples

```bash
# Install
pip install llmstxt-social

# Basic usage
llmstxt generate https://example-charity.org.uk

# Specify output
llmstxt generate https://example-charity.org.uk -o ./llms.txt

# Generate for a funder
llmstxt generate https://example-foundation.org.uk --template funder

# Skip Charity Commission enrichment
llmstxt generate https://example.org.uk --no-enrich

# Validate a file
llmstxt validate ./llms.txt

# Preview crawl
llmstxt preview https://example.org.uk
```

## Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
```

## Testing

Write tests for:
1. `test_crawler.py` - Mock HTTP responses, test sitemap parsing, robots.txt handling
2. `test_extractor.py` - Test HTML parsing, page classification, contact extraction
3. `test_generator.py` - Test output format matches spec
4. `test_validator.py` - Test validation catches spec violations

Use pytest with pytest-asyncio for async tests.

## Quality Standards

- Type hints throughout
- Docstrings for public functions
- Handle errors gracefully with helpful messages
- Use `rich` for pretty terminal output
- Follow ruff defaults for linting

## MVP Scope

For the MVP, focus on:
1. ✅ Static site crawling (no JS rendering)
2. ✅ Charity template
3. ✅ Funder template  
4. ✅ Claude API for analysis
5. ✅ Basic validation
6. ⏳ Charity Commission enrichment (nice to have for MVP)

Skip for now:
- Playwright/JS rendering
- 360Giving integration
- Other model providers (OpenAI, Ollama)
- WordPress plugin

## Example Output

When run against a charity website, the tool should produce output like:

```
$ llmstxt generate https://example-refugee-support.org.uk

🔍 Crawling https://example-refugee-support.org.uk...
  Found robots.txt ✓
  Found sitemap.xml ✓
  Fetching 24 pages...
  ████████████████████████ 100% 24/24

📄 Extracting content...
  Classified: 2 about, 4 services, 1 contact, 3 news, 14 other

🔎 Found charity number: 1234567
  Fetching Charity Commission data... ✓

🤖 Analyzing with Claude...
  Identified: Refugee support charity in Sunderland

✨ Generating llms.txt...

✅ Validation passed (9/10 completeness)

📁 Written to ./llms.txt (2.4 KB)
```

## Getting Started

1. Create the project structure
2. Set up pyproject.toml with dependencies
3. Implement modules in order: crawler → extractor → analyzer → generator → validator → cli
4. Test against 2-3 real charity websites
5. Iterate on prompts based on output quality

Good luck! Start with the crawler and work your way up.
