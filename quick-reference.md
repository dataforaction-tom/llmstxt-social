# llmstxt-social Quick Reference

## llms.txt Format (from llmstxt.org)

```markdown
# Name (H1 - required)

> One-line description (blockquote)

Context paragraph(s)

## Section Name (H2)

- [Link Title](url): Description
- [Link Title](url): Description

## Optional

- [Less important](url): Can be skipped
```

## Our Extensions

**Charity template adds:**
- `## For Funders` - registration, income, themes, geography
- `## For AI Systems` - guidance for AI representation

**Funder template adds:**
- `## For Applicants` - grant sizes, eligibility, deadlines, success rate
- `## What Makes a Strong Application`
- `## For AI Systems`
- Transparency score comment

## Module Order

1. `crawler.py` - httpx + BeautifulSoup, respect robots.txt
2. `extractor.py` - Parse HTML, classify pages, extract contacts
3. `analyzer.py` - Claude API, return structured JSON
4. `generator.py` - JSON → llms.txt markdown
5. `validator.py` - Check spec compliance
6. `cli.py` - Typer CLI, tie it together

## Key Data Classes

```python
# Crawling
Page(url, title, html, status_code)
CrawlResult(base_url, pages, robots_txt, sitemap_urls)

# Extraction  
PageType(HOME, ABOUT, SERVICES, CONTACT, GET_HELP, ...)
ExtractedPage(url, title, description, headings, body_text, page_type, contact_info, charity_number)

# Analysis
OrganisationAnalysis(name, org_type, registration_number, mission, description, services, ...)
FunderAnalysis(name, funder_type, programmes, grant_sizes, who_can_apply, success_factors, ...)

# Validation
ValidationResult(valid, issues, spec_compliance, completeness, transparency_score)
```

## CLI Commands

```bash
llmstxt generate <url> [--output] [--template charity|funder] [--model] [--max-pages] [--enrich/--no-enrich]
llmstxt validate <path> [--template]
llmstxt preview <url> [--max-pages]
```

## Page Classification Keywords

| PageType | URL patterns | Title/content keywords |
|----------|-------------|----------------------|
| ABOUT | /about, /who-we-are | about us, our story, history |
| SERVICES | /services, /what-we-do | services, programmes, support |
| CONTACT | /contact | contact, get in touch, find us |
| GET_HELP | /get-help, /support, /referral | get help, access, referral |
| DONATE | /donate, /support-us, /give | donate, support us, give |
| VOLUNTEER | /volunteer | volunteer, get involved |
| NEWS | /news, /blog | news, blog, updates |
| FUNDING_PRIORITIES | /priorities, /what-we-fund | priorities, focus areas |
| HOW_TO_APPLY | /apply, /application | apply, application, how to |
| ELIGIBILITY | /eligibility, /who-can-apply | eligibility, criteria |

## Charity Number Regex

```python
patterns = [
    r'registered charity (?:no\.?|number:?)?\s*(\d{6,7})',
    r'charity (?:no\.?|number:?)?\s*(\d{6,7})',
    r'charity registration:?\s*(\d{6,7})',
]
```

## Dependencies

```
httpx>=0.27
beautifulsoup4>=4.12
lxml>=5.0
anthropic>=0.40
typer>=0.12
rich>=13.0
pydantic>=2.0
python-dotenv>=1.0
```

## Test Sites

Pick 2-3 sites you know well to validate output quality.
