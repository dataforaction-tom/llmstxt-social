# llmstxt-core

Core library for generating and assessing llms.txt files for UK social sector organisations.

This package contains all the business logic shared between the CLI tool and SaaS platform:

- Website crawling and content extraction
- LLM-powered content analysis
- llms.txt generation with multiple templates
- Quality assessment engine
- Data enrichment (Charity Commission, 360Giving)

## Installation

```bash
pip install -e .
```

## Usage

This is a library package meant to be imported by other applications. See the CLI package (`packages/cli`) for command-line usage.

```python
from llmstxt_core.crawler import crawl_site
from llmstxt_core.extractor import extract_content
from llmstxt_core.analyzer import analyze_organisation
from llmstxt_core.generator import generate_llmstxt

# Crawl website
crawl_result = await crawl_site("https://example-charity.org.uk", max_pages=30)

# Extract content
pages = [extract_content(page) for page in crawl_result.pages]

# Analyze with Claude
analysis = await analyze_organisation(pages, template="charity")

# Generate llms.txt
llmstxt_content = generate_llmstxt(analysis, pages, template="charity")
```

## Templates

Supports 4 organization templates:
- `charity` - UK charities and VCSE organizations
- `funder` - Funders and foundations
- `public_sector` - Local authorities and NHS trusts
- `startup` - Social enterprises and startups

## License

MIT
