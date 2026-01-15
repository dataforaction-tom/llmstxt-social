# llmstxt-social

> Generate and assess llms.txt files for UK social sector organisations

A Python CLI tool that automatically generates [llms.txt](https://llmstxt.org) files for UK charities, VCSE organisations, funders, public sector bodies, and startups. Crawls websites, extracts content, analyzes with Claude, and generates spec-compliant llms.txt files with comprehensive quality assessment.

## Deploy the SaaS Platform

Deploy the full SaaS platform (API + Web + Worker) with one click:

[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/dataforaction-tom/llmstxt-social/tree/main&refcode=)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/llmstxt-social?referralCode=)

**Required after deployment:**
1. Add your `ANTHROPIC_API_KEY` in the environment variables
2. Run database migrations: `alembic upgrade head`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.

## Features

- 🕷️ **Smart crawling**: Respects robots.txt, uses sitemaps, discovers pages intelligently
- 🎭 **JavaScript support**: Playwright integration for JavaScript-heavy websites
- 📄 **Content extraction**: Parses HTML, classifies pages, extracts structured data
- 🤖 **AI-powered analysis**: Uses Claude to analyze content and generate accurate descriptions
- ✅ **Quality assessment**: Comprehensive evaluation of llms.txt completeness and quality
- 🎯 **Multiple templates**: Specialized templates for charities, funders, public sector, and startups
- 💰 **Data enrichment**:
  - Charity Commission API integration for official charity data
  - 360Giving data enrichment for funders
  - Size-based expectations for charities
- 📊 **Rich CLI output**: Beautiful progress bars, validation reports, and assessment summaries
- 📈 **Detailed reports**: JSON and Markdown assessment reports with actionable recommendations

## Repository Structure

This is a monorepo containing both an open-source CLI and a commercial SaaS platform:

- **`packages/core/`** - Core library (`llmstxt-core`) with all business logic
- **`packages/cli/`** - CLI tool (`llmstxt-social`) - open-source, MIT licensed
- **`packages/api/`** - FastAPI backend for SaaS platform
- **`packages/web/`** - React frontend for SaaS platform

The core library is shared between the CLI and SaaS platform, ensuring consistent behavior and easy maintenance. Updates to templates and generation logic automatically benefit both platforms.

## Installation

### From PyPI (when published)

```bash
pip install llmstxt-social
```

### From source (CLI tool)

```bash
git clone https://github.com/dataforaction-tom/llmstxt-social.git
cd llmstxt-social

# Install both core and CLI packages
cd packages/core && pip install -e . && cd ../..
cd packages/cli && pip install -e . && cd ../..

# If you want to use Playwright for JavaScript sites:
playwright install chromium
```

### For development

```bash
# Start local PostgreSQL and Redis (for API development)
docker-compose up -d postgres redis
```

### SaaS Platform (Full Stack)

To run the complete SaaS platform (API + Web frontend + Background workers):

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (minimum required)

# 2. Generate package-lock.json for web (required for Docker build)
cd packages/web && npm install && cd ../..

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec api alembic upgrade head

# 5. Access the platform
# - Web Frontend: http://localhost:3000
# - API Docs: http://localhost:8000/docs
# - API Health: http://localhost:8000/health
```

**Troubleshooting:**

- **"npm ci" fails during Docker build**: Run `cd packages/web && npm install` to generate `package-lock.json`
- **"relation already exists" during migrations**: Run `docker-compose exec api alembic stamp head` to mark migrations as applied
- **Rate limit errors (429)**: Clear rate limits with `docker-compose exec redis redis-cli FLUSHALL`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Dependencies

- Python 3.11+
- Anthropic API key (Claude)
- Optional: Charity Commission API key
- Optional: Playwright (for JavaScript-rendered sites)
- For SaaS Platform: Docker & Docker Compose

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

# For a public sector organization
llmstxt generate https://example-council.gov.uk --template public_sector

# For a startup
llmstxt generate https://example-startup.com --template startup
```

3. **Assess quality and completeness**:

```bash
# Assess from website (generates and evaluates)
llmstxt assess https://example-charity.org.uk

# Assess existing file
llmstxt assess ./llms.txt
```

4. **Validate an existing llms.txt file**:

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
- `-t, --template TEXT` - Template: `charity`, `funder`, `public_sector`, or `startup` (default: `charity`)
- `-m, --model TEXT` - Claude model to use (default: `claude-sonnet-4-20250514`)
- `--max-pages INTEGER` - Maximum pages to crawl (default: 30)
- `--enrich/--no-enrich` - Fetch Charity Commission data (default: `--enrich`)
- `--enrich-360/--no-enrich-360` - Fetch 360Giving data for funders (default: `--no-enrich-360`)
- `--playwright/--no-playwright` - Use Playwright for JavaScript sites (default: `--no-playwright`)
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

# Use Playwright for JavaScript-heavy sites
llmstxt generate https://js-heavy-site.org.uk --playwright

# Enrich funder with 360Giving data
llmstxt generate https://example-trust.org.uk --template funder --enrich-360

# Disable Charity Commission enrichment
llmstxt generate https://example.org.uk --no-enrich
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

### Assess Quality

Comprehensive quality assessment of llms.txt files:

```bash
llmstxt assess <URL_OR_PATH> [OPTIONS]
```

**Options:**

- `-t, --template TEXT` - Template type (auto-detected if not specified)
- `-o, --output PATH` - Output file path (default: `assessment-{timestamp}`)
- `-f, --format TEXT` - Output format: `json`, `markdown`, or `both` (default: `both`)
- `--deep/--quick` - Use Claude for quality analysis (default: `--deep`)
- `--enrich/--no-enrich` - Fetch enrichment data for context (default: `--enrich`)

**Examples:**

```bash
# Assess from website (generates llms.txt then assesses it)
llmstxt assess https://example-charity.org.uk

# Assess existing file
llmstxt assess ./llms.txt

# Quick assessment without AI analysis
llmstxt assess ./llms.txt --quick

# Output only JSON
llmstxt assess https://example.org.uk -f json -o my-assessment

# Assess without crawling for gaps
llmstxt assess ./llms.txt --no-enrich
```

**Assessment Output:**

The assess command generates:
- **JSON report**: Machine-readable assessment data with scores, findings, and recommendations
- **Markdown report**: Human-readable formatted report with detailed analysis
- **Terminal summary**: Color-coded scores and top recommendations

**What it checks:**
- ✅ Structural compliance with llms.txt spec
- ✅ Completeness of required sections
- ✅ Content quality and clarity (with AI analysis)
- ✅ Size-appropriate expectations (for charities based on income)
- ✅ Website data gaps (missing pages, no sitemap)
- ✅ Template-specific requirements

**Scoring:**
- **Overall Score** (0-100): Weighted average of completeness and quality
- **Completeness Score**: Percentage of required sections present and filled
- **Quality Score**: Content clarity, usefulness, and accuracy
- **Grade**: A (90+), B (80-89), C (70-79), D (60-69), F (<60)

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

## Projects

- Project Name (Location): What the project does

## Impact

- Beneficiaries served: Number of people helped
- Key outcomes and achievements

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

### Public Sector Template

```markdown
# Organisation Name

> One-sentence mission

Local Authority / NHS Trust / Government Department. Description.

## About

- [About Us](url): Description

## Services

### Service Category

- Service Name: Description (Eligibility: Who can access)

## Get Help

- [Contact](url): How to reach services

## Contact

- Area covered: Geographic area
- Email: email@example.gov.uk
- Phone: 0123 456 7890

## For Service Users

- Service standards and accessibility information
- Complaints procedures

## For AI Systems

When representing this organisation:
- Verify current service availability
- Direct urgent queries to official channels
```

### Startup Template

```markdown
# Company Name

> One-sentence mission

Company description and value proposition.

## About

- [About Us](url): Company overview
- Team: Founder highlights

## Product/Services

Product description and features.

## Customers

Target customers: Customer segments

- [Case Studies](url): Customer stories

## Pricing

Pricing model description.

## For Investors

- Stage: Seed / Series A / etc.
- Funding raised: Amount
- Business model: B2B SaaS / etc.
- Traction metrics: Users, revenue, growth

## Contact

- Email: hello@example.com
- Sales: sales@example.com
- Investor relations: investors@example.com

## For AI Systems

When representing this company:
- Accurately describe the product category
- Don't speculate about funding or valuation
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
git clone https://github.com/dataforaction-tom/llmstxt-social.git
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
llmstxt-social/                      # Monorepo root
├── packages/
│   ├── core/                        # Core library (shared)
│   │   ├── src/llmstxt_core/
│   │   │   ├── __init__.py
│   │   │   ├── crawler.py          # Website crawling
│   │   │   ├── crawler_playwright.py
│   │   │   ├── extractor.py        # Content extraction
│   │   │   ├── analyzer.py         # LLM analysis
│   │   │   ├── generator.py        # llms.txt generation
│   │   │   ├── validator.py        # Spec validation
│   │   │   ├── assessor.py         # Quality assessment
│   │   │   ├── enrichers/
│   │   │   │   ├── charity_commission.py
│   │   │   │   └── threesixty_giving.py
│   │   │   └── templates/
│   │   │       ├── charity.py      # Charity template
│   │   │       ├── funder.py       # Funder template
│   │   │       ├── public_sector.py
│   │   │       └── startup.py
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── cli/                         # CLI tool (open-source)
│   │   ├── src/llmstxt_social/
│   │   │   ├── __init__.py
│   │   │   └── cli.py              # CLI interface
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── api/                         # FastAPI backend
│   │   ├── src/llmstxt_api/
│   │   │   ├── main.py             # FastAPI app
│   │   │   ├── config.py           # Settings
│   │   │   ├── database.py         # DB connection
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   ├── routes/             # API endpoints
│   │   │   ├── services/           # Business logic
│   │   │   └── tasks/              # Celery background jobs
│   │   ├── alembic/                # Database migrations
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── README.md
│   │
│   └── web/                         # React frontend
│       ├── src/
│       │   ├── App.tsx
│       │   ├── pages/              # React pages
│       │   ├── components/         # React components
│       │   ├── api/                # API client
│       │   └── types/              # TypeScript types
│       ├── public/
│       ├── Dockerfile
│       └── README.md
│
├── docs/
│   └── saas-architecture.md        # SaaS platform architecture
│
├── DEPLOYMENT.md                   # Deployment guide
├── docker-compose.yml              # Local development environment
├── .env.example                    # Environment configuration template
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

## Data Enrichment

### Charity Commission Integration

Automatically fetches official data from the UK Charity Commission:

- Official charity name and status
- Registration date and charity number
- Latest financial information (income/expenditure)
- Charitable objects and activities
- Trustee information
- Contact details

**Setup:**

1. (Optional) Get an API key from [Charity Commission Developer Portal](https://developer.charitycommission.gov.uk/)
2. Add to `.env`: `CHARITY_COMMISSION_API_KEY=your-key-here`
3. If no API key is provided, falls back to scraping the public register

**Usage:**
```bash
# Enabled by default
llmstxt generate https://example-charity.org.uk

# Disable if not needed
llmstxt generate https://example-charity.org.uk --no-enrich
```

### 360Giving Data (Funders)

Enriches funder profiles with open grants data from [360Giving](https://www.threesixtygiving.org/):

- Total grants awarded and amounts
- Average grant size and range
- Geographic distribution
- Funding themes and priorities
- Sample recipients
- Grants over time trends

**Usage:**
```bash
llmstxt generate https://example-foundation.org.uk --template funder --enrich-360
```

### Playwright for JavaScript Sites

Some modern charity and funder websites use JavaScript frameworks (React, Vue, etc.) that require browser rendering:

**Setup:**
```bash
playwright install chromium
```

**Usage:**
```bash
llmstxt generate https://js-heavy-site.org.uk --playwright
```

**When to use:**
- Site appears blank when crawled normally
- Content loads dynamically after page load
- Single-page applications (SPAs)

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Required: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Charity Commission API
CHARITY_COMMISSION_API_KEY=your-key-here

# Stripe (required for payments)
STRIPE_SECRET_KEY=sk_test_your-key-here
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_MONITORING_PRICE_ID=price_your-subscription-price-id

# Frontend
VITE_STRIPE_PUBLIC_KEY=pk_test_your-key-here
```

### Stripe Setup

To enable payments for the SaaS platform:

1. **Create a Stripe account** at [stripe.com](https://stripe.com)

2. **Get your API keys** from the [Stripe Dashboard](https://dashboard.stripe.com/apikeys):
   - Copy the **Secret key** (starts with `sk_test_` or `sk_live_`)
   - Copy the **Publishable key** (starts with `pk_test_` or `pk_live_`)

3. **Create a subscription product** for monitoring:
   - Go to Products > Add product
   - Name: "llms.txt Monitoring"
   - Price: £9.00/month (recurring)
   - Copy the **Price ID** (starts with `price_`)

4. **Set up webhooks**:
   - Go to Developers > Webhooks > Add endpoint
   - Endpoint URL: `https://yourdomain.com/api/payment/webhook`
   - Events to listen for:
     - `payment_intent.succeeded`
     - `payment_intent.payment_failed`
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`
   - Copy the **Signing secret** (starts with `whsec_`)

5. **For local development**, use Stripe CLI:
   ```bash
   stripe listen --forward-to localhost:8000/api/payment/webhook
   ```

6. **Add environment variables** to `.env`:
   ```bash
   STRIPE_SECRET_KEY=sk_test_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_MONITORING_PRICE_ID=price_xxx
   VITE_STRIPE_PUBLIC_KEY=pk_test_xxx
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

### v0.3.0 (Current) - SaaS Platform MVP
- ✅ **CLI Tool (Open Source)**
  - Static site crawling
  - 4 templates (charity, funder, public_sector, startup)
  - Quality assessment system
  - Charity Commission API integration
  - 360Giving data enrichment
  - JavaScript-rendered sites (Playwright)
  - Size-based expectations
  - Website gap analysis
  - AI-powered quality analysis
  - JSON and Markdown reports

- ✅ **SaaS Platform**
  - FastAPI backend with async PostgreSQL
  - React frontend (TypeScript + Tailwind CSS)
  - Celery background job processing
  - Stripe payment integration (test mode)
  - Free tier (10 generations/day, basic output)
  - Paid tier (£29, includes assessment + enrichment)
  - Rate limiting middleware
  - Real-time job status updates
  - Docker deployment configuration

### v0.4.0 (Current)
- ✅ SaaS Platform: Subscription tier (£9/month)
- ✅ SaaS Platform: Automated monitoring and regeneration
- ✅ SaaS Platform: User dashboard
- ✅ SaaS Platform: Change history tracking
- ✅ SaaS Platform: Stripe payment verification
- ✅ SaaS Platform: Celery beat scheduler for monitoring

### v0.5.0 (Next)
- [ ] SaaS Platform: Production deployment
- [ ] SaaS Platform: Email notifications for changes
- [ ] API: Public API access
- [ ] CLI: Alternative LLM providers (OpenAI, Ollama)
- [ ] CLI: Batch processing

### Future
- [ ] WordPress plugin
- [ ] Assessment history tracking and comparison
- [ ] Zapier/Make.com integrations
- [ ] White-label options for agencies

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgements

- Built for the [llmstxt.org](https://llmstxt.org) specification
- Powered by [Anthropic's Claude](https://www.anthropic.com)
- Designed for the UK social sector

## Support

- **Issues**: [GitHub Issues](https://github.com/dataforaction-tom/llmstxt-social/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dataforaction-tom/llmstxt-social/discussions)

---

Made with ❤️ for the social sector
