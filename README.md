# llmstxt-social

> Generate llms.txt files for UK social sector organisations

A Python CLI tool that automatically generates [llms.txt](https://llmstxt.org) files for UK charities, VCSE organisations, and funders. Crawls websites, extracts content, analyzes with Claude, and generates spec-compliant llms.txt files with social sector-specific extensions.

## Features

- 🕷️ **Smart crawling**: Respects robots.txt, uses sitemaps, discovers pages intelligently
- 📄 **Content extraction**: Parses HTML, classifies pages, extracts structured data
- 🤖 **AI-powered analysis**: Uses Claude to analyze content and generate accurate descriptions
- ✅ **Validation**: Checks compliance with llmstxt.org spec
- 🎯 **Social sector templates**: Specialized templates for charities and funders
- 📊 **Rich CLI output**: Beautiful progress bars and validation reports

## Installation

### From PyPI (when published)

```bash
pip install llmstxt-social
```

### From source

```bash
git clone https://github.com/yourusername/llmstxt-social.git
cd llmstxt-social
pip install -e .
```

### Dependencies

- Python 3.11+
- Anthropic API key (Claude)

## Quick Start

1. **Set up your API key**:

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

2. **Generate an llms.txt file**:

```bash
# For a charity
llmstxt generate https://example-charity.org.uk

# For a funder
llmstxt generate https://example-foundation.org.uk --template funder
```

3. **Validate an existing llms.txt file**:

```bash
llmstxt validate ./llms.txt
```

## Usage

### Generate llms.txt

```bash
llmstxt generate <URL> [OPTIONS]
```

**Options:**

- `-o, --output PATH` - Output file path (default: `./llms.txt`)
- `-t, --template TEXT` - Template: `charity` or `funder` (default: `charity`)
- `-m, --model TEXT` - Claude model to use (default: `claude-sonnet-4-20250514`)
- `--max-pages INTEGER` - Maximum pages to crawl (default: 30)
- `--enrich/--no-enrich` - Fetch Charity Commission data (default: `--no-enrich`)
- `--charity TEXT` - Specify charity number directly

**Examples:**

```bash
# Basic usage
llmstxt generate https://refugee-support.org.uk

# Specify output location
llmstxt generate https://refugee-support.org.uk -o ./output/llms.txt

# Generate for a funder
llmstxt generate https://example-trust.org.uk --template funder

# Limit crawl depth
llmstxt generate https://example.org.uk --max-pages 15

# Use faster model
llmstxt generate https://example.org.uk --model claude-haiku-3-5-20250219
```

### Validate llms.txt

```bash
llmstxt validate <PATH_OR_URL> [OPTIONS]
```

**Options:**

- `-t, --template TEXT` - Template to validate against: `charity` or `funder`

**Examples:**

```bash
# Validate local file
llmstxt validate ./llms.txt

# Validate from URL
llmstxt validate https://example.org.uk/llms.txt

# Validate against funder template
llmstxt validate ./llms.txt --template funder
```

### Preview crawl

Preview what pages would be crawled without generating llms.txt:

```bash
llmstxt preview <URL> [OPTIONS]
```

**Examples:**

```bash
llmstxt preview https://example.org.uk
llmstxt preview https://example.org.uk --max-pages 50
```

## Output Format

### Charity Template

```markdown
# Charity Name

> One-sentence mission statement

Charity type, registration number. 2-3 sentence description.

## About

- [About Us](url): Description
- [Our Team](url): Description

## Services

- [Service Name](url): What the service provides

## Get Help

- [Access Support](url): How to access services
- [Contact](url): Contact information

## Get Involved

- [Volunteer](url): Volunteering opportunities
- [Donate](url): Support our work

## For Funders

- Registration: 1234567
- Geography: Area served
- Themes: theme1, theme2
- Beneficiaries: Who is served
- Contact: email@example.org

## For AI Systems

When representing this organisation:
- Guidance for AI systems
- Important context and caveats
```

### Funder Template

```markdown
# Foundation Name

> One-sentence funding mission

Funder type, registration number. 2-3 sentence description.

## About

- [About Us](url): Description

## What We Fund

- [Funding Priorities](url): Thematic areas
- [Programme Name](url): Description

## How to Apply

- [Application Process](url): How to apply
- [Eligibility](url): Who can apply

## For Applicants

- Geographic focus: Where they fund
- Themes: theme1, theme2
- Grant sizes: £1,000-£25,000
- Who can apply: Eligible organisation types
- Who cannot apply: Restrictions
- Contact: grants@example.org

## For AI Systems

When representing this funder:
- Never guarantee funding outcomes
- Verify current criteria before advising
```

## Validation

The validator checks:

### Core Spec Compliance

- ✅ H1 heading at start
- ✅ Blockquote after H1
- ✅ Sections use H2 headings
- ✅ Valid markdown link format
- ✅ No duplicate H1 headings

### Template-Specific

**Charity:**
- Recommended sections (About, Services, For Funders, For AI Systems)
- Contact information present
- Completeness score

**Funder:**
- Recommended sections (What We Fund, How to Apply, For Applicants)
- Transparency score (Basic / Transparent / Open)
- Application guidance present

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/llmstxt-social.git
cd llmstxt-social

# Install with dev dependencies
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check .
ruff format .
```

## Project Structure

```
llmstxt-social/
├── src/llmstxt_social/
│   ├── __init__.py
│   ├── cli.py              # CLI interface
│   ├── crawler.py          # Website crawling
│   ├── extractor.py        # Content extraction
│   ├── analyzer.py         # LLM analysis
│   ├── generator.py        # llms.txt generation
│   ├── validator.py        # Spec validation
│   ├── enrichers/
│   │   ├── __init__.py
│   │   └── charity_commission.py
│   └── templates/
│       ├── __init__.py
│       ├── charity.py      # Charity template
│       └── funder.py       # Funder template
├── tests/
│   ├── test_extractor.py
│   ├── test_generator.py
│   └── test_validator.py
├── pyproject.toml
├── README.md
└── LICENSE
```

## How It Works

1. **Crawl**: Fetches pages from the website
   - Respects robots.txt
   - Uses sitemap.xml if available
   - Falls back to link discovery
   - Rate-limited (1 req/sec)

2. **Extract**: Parses HTML and extracts content
   - Removes navigation, scripts, styles
   - Classifies page types (about, services, contact, etc.)
   - Extracts contact information
   - Finds charity numbers

3. **Analyze**: Uses Claude to analyze content
   - Identifies organisation details
   - Extracts services/programmes
   - Generates descriptions
   - Produces AI guidance

4. **Generate**: Creates llms.txt
   - Follows llmstxt.org spec
   - Uses social sector templates
   - Groups pages by type
   - Formats as markdown

5. **Validate**: Checks compliance
   - Validates structure
   - Checks completeness
   - Calculates scores
   - Reports issues

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Required: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Charity Commission API
# CHARITY_COMMISSION_API_KEY=your-key-here
```

### Model Selection

Choose different Claude models based on your needs:

- `claude-sonnet-4-20250514` - Best quality (default)
- `claude-haiku-3-5-20250219` - Faster, cheaper

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Roadmap

MVP (Current):
- ✅ Static site crawling
- ✅ Charity template
- ✅ Funder template
- ✅ Claude analysis
- ✅ Basic validation

Future:
- [ ] Charity Commission API integration
- [ ] 360Giving data enrichment
- [ ] JavaScript-rendered sites (Playwright)
- [ ] Alternative LLM providers (OpenAI, Ollama)
- [ ] WordPress plugin
- [ ] Batch processing

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgements

- Built for the [llmstxt.org](https://llmstxt.org) specification
- Powered by [Anthropic's Claude](https://www.anthropic.com)
- Designed for the UK social sector

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/llmstxt-social/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/llmstxt-social/discussions)

---

Made with ❤️ for the social sector
