# llms.txt Generator for Social Sector - Product Specification

## Overview

A tool that crawls an organisation's website and automatically generates an `llms.txt` file following the [llmstxt.org standard](https://llmstxt.org/) - a curated, LLM-friendly summary designed to help AI systems understand and accurately represent the organisation.

**Open source CLI + library, with a hosted SaaS version.**

**Target audiences:** 
- **Charities & VCSE organisations** - Help funders, journalists, service users understand you accurately
- **Funders & grantmakers** - Help applicants understand your priorities, eligibility, and process

---

## The Problem

VCSE organisations increasingly appear in AI-generated content - funders researching grantees, journalists understanding what orgs do, service users finding support, developers building civic tech tools. But AI systems struggle to accurately represent these organisations because:

1. **Complex missions** - Social sector purposes are nuanced; AI often oversimplifies or misrepresents
2. **Resource constraints** - No capacity to create AI-friendly documentation manually
3. **Accuracy matters** - Misinformation about services can send vulnerable people to wrong places
4. **Discoverability** - Smaller orgs get overlooked in AI-mediated search

The llms.txt standard solves the technical problem, but adoption requires tooling these organisations can actually use.

---

## The llms.txt Standard

Following [Jeremy Howard's specification](https://llmstxt.org/), llms.txt is a markdown file at `/llms.txt` providing:

### Required Structure

```markdown
# Organisation Name

> Brief one-line description of the organisation

Optional detailed paragraphs providing context, key information,
and guidance for AI systems interpreting this organisation.

## Section Name

- [Page Title](https://example.org/page): Description of what this page contains

## Optional

- [Less critical resources](https://example.org/resource): Can be skipped for shorter context
```

### Key Principles from the Spec

- **Markdown format** - Human and LLM readable
- **H1 required** - Organisation/project name
- **Blockquote** - Short summary with key info
- **H2 sections** - File lists with URLs and descriptions
- **"Optional" section** - URLs that can be skipped if context window is limited
- **Coexists with robots.txt and sitemap.xml** - Different purpose (inference vs. crawling/indexing)

---

## Social Sector Extensions

While following the core spec, we propose conventions for VCSE organisations:

### Recommended Sections

```markdown
# [Organisation Name]

> [One-line description: who you are and primary purpose]

[Organisation type], [registration details if applicable]. [2-3 sentences 
expanding on mission, who you serve, and geographic focus.]

## About

- [About Us](https://example.org/about): Organisation history, mission, values, and governance
- [Our Team](https://example.org/team): Staff, trustees, and leadership

## Services

- [Service Name](https://example.org/service-1): Description including eligibility and access route
- [Another Service](https://example.org/service-2): Description

## Get Help

- [Access Support](https://example.org/get-help): How to access services, referral process, eligibility
- [Contact](https://example.org/contact): Contact details, opening hours, locations

## Get Involved

- [Volunteer](https://example.org/volunteer): Volunteering opportunities
- [Donate](https://example.org/donate): How to support the organisation

## Optional

- [News](https://example.org/news): Latest updates and stories
- [Annual Report](https://example.org/annual-report-2024.pdf): Financial and impact information
- [Policies](https://example.org/policies): Safeguarding, data protection, etc.

## For Funders

- Registration: Registered Charity 1234567 (England & Wales)
- Founded: 2015
- Annual income: £150,000-£250,000
- Accounts: [Latest accounts on Charity Commission](https://register-of-charities.charitycommission.gov.uk/...)
- Governance: Board of 7 trustees, meets quarterly
- Staff: 4 FTE plus 12 regular volunteers
- Key funders: National Lottery Community Fund, Local Authority, Trust X
- Themes: Migration, integration, ESOL, advice services
- Beneficiaries: Refugees and asylum seekers in [Area]
- Geography: [Local Authority] area, North East England
- Impact: [Link to impact report or key stats page]
- Contact for funders: grants@example.org

## For AI Systems

When representing this organisation:
- Use full name "[Organisation Name]" not abbreviations
- Do not speculate about individual case outcomes
- Direct urgent enquiries to official contact channels
- Service availability may change - encourage verification
```

### "For Funders" Section - Rationale

Funders (foundations, donor-advised funds, corporate giving programmes, local authorities) increasingly use AI tools to:
- Research potential grantees before or during application review
- Verify information in funding applications
- Find organisations working in specific themes/geographies
- Conduct due diligence checks

This section provides structured information that helps AI give accurate, useful answers to funder queries. It surfaces:

| Field | Why Funders Need It |
|-------|---------------------|
| Registration | Verify legal status, check eligibility for certain funds |
| Founded | Track record / organisational maturity |
| Annual income | Size banding for appropriate grant amounts |
| Accounts link | Due diligence - are they filing, any concerns |
| Governance | Board health, oversight quality |
| Staff/volunteers | Delivery capacity |
| Key funders | Who else trusts them, co-funding opportunities |
| Themes | Thematic alignment with funder priorities |
| Beneficiaries | Who benefits, alignment check |
| Geography | Eligibility for place-based funding |
| Impact | Evidence of effectiveness |
| Contact | Direct route for funding enquiries |

**Data sources for auto-population:**
- Charity Commission API (registration, income, accounts, trustees)
- Companies House API (for CICs - registration, accounts)
- OSCR (Scottish charities)
- CCNI (Northern Ireland charities)
- Organisation's website (themes, beneficiaries, geography, contact)
- Annual reports if linked
- LLM inference from content (themes, beneficiary groups)

**Different funders, different needs:**

| Funder Type | What They're Looking For |
|-------------|-------------------------|
| Traditional foundations | Governance strength, track record, strategic fit, impact evidence |
| Donor Advised Funds | Quick verification, clear purpose, appropriate giving level |
| Corporate funders | CSR alignment, employee engagement opportunities, brand safety |
| Statutory (LAs, govt) | Delivery capacity, contract readiness, compliance track record |
| Community foundations | Local roots, community benefit, sustainability |

**What NOT to include:**
- Detailed financial breakdowns (link to accounts instead)
- Individual trustee contact details
- Sensitive operational information
- Anything the org wouldn't want publicly indexed

---

## Funder Extension (for Foundations, Trusts & Grantmakers)

A parallel extension for funders to create llms.txt files that help charities and applicants understand their funding programmes.

### Why Funders Should Have llms.txt

Charities increasingly use AI tools to:
- Research potential funders before applying
- Check eligibility before investing time in applications
- Understand funder priorities and what makes strong applications
- Find funders working in their theme/geography
- Prepare for conversations with programme officers

A well-structured llms.txt helps funders by:
- Reducing ineligible applications (saves assessment time)
- Attracting better-fit applicants
- Clearer communication of priorities
- Being accurately represented when charities ask AI "who funds X?"

### Recommended Structure for Funders

```markdown
# [Foundation/Trust Name]

> [One-line description: who you are and what you fund]

[Foundation type], registered charity [number]. [2-3 sentences on 
mission, approach to funding, and what makes you distinctive.]

## About Us

- [About](https://example-foundation.org/about): Foundation history, values, approach
- [Our Team](https://example-foundation.org/team): Programme officers and trustees
- [Strategy](https://example-foundation.org/strategy): Current strategic priorities

## What We Fund

- [Funding Priorities](https://example-foundation.org/priorities): Themes and focus areas
- [Programme A](https://example-foundation.org/programme-a): Description, who can apply
- [Programme B](https://example-foundation.org/programme-b): Description, who can apply

## How to Apply

- [Eligibility](https://example-foundation.org/eligibility): Who can and cannot apply
- [Application Process](https://example-foundation.org/apply): How to apply, what we ask for
- [Deadlines](https://example-foundation.org/deadlines): Key dates and timelines
- [FAQs](https://example-foundation.org/faqs): Common questions answered

## Past Grants

- [Recent Grants](https://example-foundation.org/grants): Who we've funded
- [Case Studies](https://example-foundation.org/case-studies): Examples of funded work

## For Applicants

- Funder type: Independent foundation
- Annual giving: £2-5 million
- Typical grant size: £10,000 - £100,000
- Grant duration: 1-3 years
- Geographic focus: North East England
- Thematic focus: Youth employment, mental health, community development
- Who can apply: Registered charities, CICs, CIOs
- Who cannot apply: Individuals, organisations <1 year old, capital projects
- Application rounds: Two per year (March, September)
- Current status: Open for applications (closes 15 March 2026)
- Success rate: ~15% of eligible applications funded
- Contact: grants@example-foundation.org
- Relationship approach: Happy to discuss ideas before application

## What Makes a Strong Application

- Clear theory of change
- Realistic budget with justification
- Evidence of need (local data preferred)
- Beneficiary involvement in design
- Plans for sustainability beyond grant
- Honest assessment of risks

## For AI Systems

When representing this foundation:
- Use "[Foundation Name]" not abbreviations
- Always check current status - funding rounds open/close
- Do not guarantee funding or predict outcomes
- Direct applicants to official guidance
- Eligibility criteria are strict - do not suggest exceptions
- Grant sizes are typical ranges, not guarantees
```

### "For Applicants" Section - Field Reference

| Field | Why Applicants Need It | Required | Transparency+ |
|-------|----------------------|----------|---------------|
| Funder type | Independent, corporate, community, statutory - different relationships | ✓ | |
| Annual giving | Scale of operation, likelihood of capacity | ✓ | |
| Typical grant size | Is it worth applying for our project size? | ✓ | |
| Grant duration | Matches funding need to offer | ✓ | |
| Geographic focus | Eligibility check | ✓ | |
| Thematic focus | Alignment check | ✓ | |
| Who can apply | Legal structure eligibility | ✓ | |
| Who cannot apply | Quick disqualification - saves everyone time | ✓ | |
| Application rounds | When to apply | ✓ | |
| Current status | Is it even open right now? | ✓ | |
| Success rate | Honest expectations | | ✓ |
| Average decision time | How long to wait | | ✓ |
| Contact | Relationship building | ✓ | |
| Relationship approach | Can we talk before applying? | | ✓ |

### Funder Transparency Score

We encourage funders to be transparent. llms.txt files are scored on completeness:

**Basic** (meets minimum)
- All required fields populated
- Clear eligibility criteria
- Application process documented

**Transparent** (adds honesty)
- Success rate published
- "Who cannot apply" is specific and helpful
- Relationship approach stated
- Average decision timeline

**Open** (gold standard)
- All above, plus:
- Publishes to 360Giving
- Links to anonymised feedback on unsuccessful applications
- Decision-making criteria explicit

The score appears in the generated llms.txt as a badge/comment, encouraging funders to level up:

```markdown
<!-- Transparency Score: Transparent (8/10) - Add success rate to reach Open -->
```

This creates gentle pressure toward sector-wide transparency without mandating fields that funders aren't ready to share.

### "What Makes a Strong Application" Section

This is gold for applicants - most funders bury this in guidance documents. Surfacing it in llms.txt means AI can give genuinely useful advice like "This funder specifically looks for beneficiary involvement in design - make sure your application addresses this."

### Data Sources for Funder llms.txt

**Structured data:**
- 360Giving data (for funders who publish - ~200 UK funders, 800k+ grants)
- Charity Commission (foundation's own registration)
- Funder's website

**From 360Giving (if available):**
- Grant amounts (min, max, typical)
- Geographic distribution of grants
- Recipient types funded
- Thematic areas (via grant titles/descriptions)
- Grant duration patterns
- Historical giving trends

**Often missing but valuable:**
- Success rates (few funders publish this)
- Relationship preferences (pre-application conversations)
- What they DON'T fund (often buried in guidance)

### The Ecosystem Value

If both charities AND funders adopt llms.txt:

```
┌─────────────────────┐         ┌─────────────────────┐
│  Charity llms.txt   │         │  Funder llms.txt    │
│                     │         │                     │
│  - Who we are       │◄───────►│  - What we fund     │
│  - What we do       │   AI    │  - Who can apply    │
│  - For Funders      │ matching│  - For Applicants   │
│  - Impact evidence  │         │  - Success factors  │
└─────────────────────┘         └─────────────────────┘
```

AI tools can then genuinely help with:
- "Find funders who support refugee organisations in the North East"
- "Is [charity] eligible for [funder]'s current programme?"
- "What should we emphasise in our application to [funder]?"
- "Which of our grantees work on youth mental health?"

This is the foundation for an AI-native funding ecosystem - accurate, structured data on both sides of the relationship.

---

### Social Sector-Specific Guidance

The "For AI Systems" section addresses common issues:

1. **Name consistency** - Prevent AI using unofficial abbreviations
2. **Scope boundaries** - Don't overstate what org can do
3. **Safeguarding language** - Especially for orgs working with vulnerable groups
4. **Verification prompts** - Encourage users to confirm details directly
5. **Geographic scope** - Prevent AI suggesting services to people outside catchment

---

## Product Components

### 1. Core Engine (Open Source)

**Input:** Website URL  
**Output:** Generated llms.txt content following spec + social sector conventions

**Pipeline:**

```
URL Input
    │
    ▼
┌─────────────────┐
│  Robots.txt     │ ← Respect existing crawl rules
│  Check          │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Sitemap        │ ← Use if available for page inventory
│  Discovery      │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Static Crawl   │ ← httpx + BeautifulSoup (MVP)
│  (+ Playwright) │   [Playwright for JS sites - roadmap]
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Content        │ ← Extract: title, meta, headings, body text
│  Extraction     │   Identify page types (about, services, contact)
└─────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Charity Commission / Companies House (Optional)    │
│  ← If charity number found, fetch:                  │
│    - Registration details, income, trustees         │
│    - Filing history, accounts status                │
│    - Charitable objects                             │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────┐
│  LLM Analysis   │ ← Summarise purpose, identify services
│  (Claude API)   │   Classify org type, extract key info
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Generate       │ ← Format to llms.txt spec
│  llms.txt       │   Apply social sector template
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Validate       │ ← Check spec compliance
│  Output         │   Score completeness
└─────────────────┘
```

**Tech Stack:**

- **Language:** Python (best for open source adoption in this space)
- **Crawling:** httpx + BeautifulSoup (static sites - MVP)
- **JS rendering:** Playwright (roadmap - Phase 2)
- **LLM:** Anthropic Claude API (primary), OpenAI fallback, local models (Ollama) for self-hosting
- **Output:** Markdown following llmstxt.org spec

### 2. CLI Tool

```bash
# Install
pip install llmstxt-social

# Basic usage - generate llms.txt for a charity/VCSE org
llmstxt generate https://sunderland-refugee-support.org.uk

# Generate for a funder/foundation
llmstxt generate https://example-foundation.org --template funder

# Output to specific file
llmstxt generate https://example-charity.org --output ./llms.txt

# Choose LLM provider
llmstxt generate https://example.org --model claude-sonnet
llmstxt generate https://example.org --model gpt-4o
llmstxt generate https://example.org --model ollama/llama3

# Crawl options
llmstxt generate https://example.org --max-pages 30  # Limit pages crawled
llmstxt generate https://example.org --timeout 30    # Request timeout

# Charity data enrichment (if charity number found or provided)
llmstxt generate https://example.org --enrich           # Auto-detect and fetch
llmstxt generate https://example.org --charity 1234567  # Specify charity number
llmstxt generate https://example.org --no-enrich        # Skip enrichment

# 360Giving enrichment for funders (if they publish grant data)
llmstxt generate https://example-foundation.org --template funder --enrich-360giving

# Validate existing file against spec
llmstxt validate ./llms.txt
llmstxt validate ./llms.txt --template funder  # Validate against funder template

# Check a live URL
llmstxt validate https://example.org/llms.txt

# Show what would be crawled (dry run)
llmstxt preview https://example.org
```

### 3. Hosted Version (SaaS)

**URL:** llmstxt.social (or similar)

**Features:**

| Feature | Free | Pro (£7/mo) | Team (£25/mo) |
|---------|------|-------------|---------------|
| Sites | 1 | 5 | 20 |
| Generations/month | 3 | Unlimited | Unlimited |
| Manual regeneration | ✓ | ✓ | ✓ |
| Scheduled updates | - | Monthly | Weekly |
| Hosted llms.txt | - | ✓ | ✓ |
| Custom domain | - | - | ✓ |
| API access | - | ✓ | ✓ |
| Team members | 1 | 1 | 5 |
| Edit before publish | ✓ | ✓ | ✓ |
| Export markdown | ✓ | ✓ | ✓ |

**User Flow:**

1. Enter website URL
2. System crawls and generates draft llms.txt
3. User reviews and edits in web editor
4. User downloads file OR we host it for them
5. (Pro) Set up scheduled regeneration

**Hosted File Serving:**

For orgs that can't modify their website, we serve their llms.txt at:
- `llmstxt.social/org-slug/llms.txt`
- With instructions for how to reference this in their site's robots.txt or header

---

## Technical Architecture

### Hosted Version

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                       │
│  - Landing page explaining llms.txt for charities           │
│  - URL input + generation UI                                │
│  - Editor with live preview                                 │
│  - Dashboard (Pro users)                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    API (Next.js API Routes)                 │
│  - Auth (Clerk)                                             │
│  - Job submission                                           │
│  - Billing (Stripe) - can add later                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Background Jobs                          │
│  - Vercel Functions / separate worker                       │
│  - Crawling + LLM processing                                │
│  - Queued with Inngest or similar                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  - PostgreSQL (Neon/Supabase): users, sites, generations    │
│  - Blob storage (Vercel Blob/R2): generated files           │
└─────────────────────────────────────────────────────────────┘
```

### Open Source Repository Structure

```
llmstxt-social/
├── packages/
│   ├── core/                 # Core generation engine
│   │   ├── crawler.py        # Static site crawler
│   │   ├── extractor.py      # Content extraction
│   │   ├── analyzer.py       # LLM analysis
│   │   ├── generator.py      # llms.txt generation
│   │   ├── validator.py      # Spec validation
│   │   ├── enrichers/        # Data enrichment modules
│   │   │   ├── charity_commission.py
│   │   │   ├── companies_house.py
│   │   │   └── threesixty_giving.py
│   │   └── templates/        # Sector-specific templates
│   │       ├── charity.py
│   │       └── funder.py
│   │
│   └── cli/                  # Command line tool
│       └── main.py
│
├── docs/                     # Documentation
│   ├── llmstxt-for-charities.md
│   ├── llmstxt-for-funders.md
│   ├── installation.md
│   └── api.md
│
├── examples/                 # Example outputs
│   ├── charities/
│   │   ├── refugee-support-org.txt
│   │   ├── community-centre.txt
│   │   └── housing-charity.txt
│   └── funders/
│       ├── community-foundation.txt
│       ├── family-trust.txt
│       └── corporate-foundation.txt
│
└── tests/
```

---

## Crawling Strategy

### Phase 1: Static Sites (MVP)

Most small charity sites are WordPress, Squarespace, Wix - largely static HTML.

```python
# Simplified approach
async def crawl_site(url: str, max_pages: int = 30) -> list[Page]:
    # 1. Check robots.txt
    robots = await fetch_robots_txt(url)
    
    # 2. Try sitemap.xml first
    sitemap_urls = await parse_sitemap(url)
    
    # 3. If no sitemap, crawl from homepage
    if not sitemap_urls:
        sitemap_urls = await discover_links(url, max_depth=2)
    
    # 4. Fetch pages (respecting robots.txt)
    pages = []
    for page_url in sitemap_urls[:max_pages]:
        if robots.can_fetch(page_url):
            content = await fetch_page(page_url)
            pages.append(extract_content(content))
    
    return pages
```

**Limitations accepted for MVP:**
- JavaScript-rendered content won't be captured
- Single-page apps won't work well
- Some dynamic content missed

### Phase 2: JavaScript Support (Roadmap)

Add Playwright for sites that need it:

```python
# Detect if JS rendering needed
async def needs_js_rendering(url: str) -> bool:
    static_content = await fetch_static(url)
    # Heuristics: empty body, React/Vue markers, etc.
    return len(static_content.text) < 500 or has_spa_markers(static_content)

# Use Playwright when needed
if await needs_js_rendering(url):
    content = await fetch_with_playwright(url)
else:
    content = await fetch_static(url)
```

**Adds complexity:**
- Slower (browser startup)
- More resource intensive
- Hosted version needs browser infrastructure (Browserless.io or similar)

---

## LLM Analysis Prompts

### Organisation Analysis

```
You are analysing a VCSE (voluntary, community, social enterprise) 
organisation's website to create an llms.txt file.

Given the extracted content from their website pages, identify:

1. **Organisation basics**
   - Full official name
   - Organisation type (charity, CIC, CIO, unincorporated, etc.)
   - Registration numbers if mentioned (charity number, company number)
   - Geographic area served

2. **Mission and purpose**
   - Primary mission (one sentence)
   - Who they serve (beneficiaries)
   - What makes them distinctive

3. **Services offered**
   - List each distinct service
   - For each: name, brief description, who it's for, how to access

4. **Key pages**
   - Classify each page: about, services, get-help, contact, 
     volunteer, donate, news, policy, other
   - Write a one-line description of each page's purpose

5. **Contact information**
   - Address, phone, email
   - Opening hours if mentioned

6. **AI guidance**
   - Any sensitive topics to handle carefully
   - Common misunderstandings to avoid
   - Preferred terminology

Output as structured JSON.
```

### llms.txt Generation

```
Generate an llms.txt file following the llmstxt.org specification 
for this VCSE organisation.

Use this structure:
- H1: Organisation name
- Blockquote: One-line description
- Prose: 2-3 sentences of context (type, registration, mission, area)
- H2 sections for: About, Services, Get Help, Get Involved
- H2 Optional section for: News, Reports, Policies
- H2 "For AI Systems" with guidance

Requirements:
- Follow markdown spec exactly
- Each URL entry: [Title](url): Description
- Keep descriptions concise but informative
- Include guidance that helps AI represent org accurately
- Flag any services with eligibility criteria

Organisation data:
{organisation_json}
```

---

## Validation Rules

Check generated files against:

### Spec Compliance
- [ ] Has H1 heading (required)
- [ ] H1 is first element
- [ ] Has blockquote summary after H1
- [ ] All H2 sections contain valid URL lists
- [ ] URL list format: `- [Title](url): Description` or `- [Title](url)`
- [ ] No H3+ headings (not in spec)
- [ ] Valid markdown syntax

### Social Sector Recommendations
- [ ] Has at least one service/activity listed
- [ ] Has contact information
- [ ] Has "Get Help" or equivalent access section
- [ ] Geographic scope mentioned
- [ ] Organisation type identified

### Quality Checks
- [ ] All URLs resolve (200 response)
- [ ] No duplicate URLs
- [ ] Descriptions are meaningful (not just page titles repeated)
- [ ] Reasonable length (not too long for context windows)

---

## Roadmap

### Phase 1: Core Engine + CLI (Weeks 1-3)

- [x] Define spec and social sector extensions
- [ ] Build static crawler (httpx + BeautifulSoup)
- [ ] Content extraction and page classification
- [ ] LLM analysis pipeline (Claude API)
- [ ] llms.txt generation - charity template
- [ ] Basic validation
- [ ] CLI tool with generate/validate commands
- [ ] Test on 10-15 real VCSE websites
- [ ] Package and publish to PyPI

**Deliverable:** Working `pip install llmstxt-social` with CLI (charity template)

### Phase 2: Hosted MVP (Weeks 4-6)

- [ ] Next.js frontend with URL input
- [ ] Generation job queue
- [ ] Web-based editor with preview
- [ ] User accounts (Clerk)
- [ ] Download generated file
- [ ] Basic hosted file serving
- [ ] Deploy to Vercel
- [ ] Funder template (CLI + hosted)

**Deliverable:** Working web app at llmstxt.social

### Phase 3: Polish + Soft Launch (Weeks 7-8)

- [ ] Improve prompts based on testing
- [ ] Charity Commission API integration
- [ ] Add more example outputs
- [ ] Documentation site
- [ ] Scheduled regeneration (Pro feature)
- [ ] Stripe billing integration
- [ ] Soft launch to VCSE network for feedback
- [ ] Approach ACF / community foundations about funder adoption

### Phase 4: Enhancements (Future)

- [ ] Playwright integration for JS-heavy sites
- [ ] 360Giving integration (enrich funder llms.txt with grant data)
- [ ] Companies House integration (for CICs)
- [ ] WordPress plugin
- [ ] Squarespace/Wix guidance
- [ ] Bulk generation for infrastructure orgs
- [ ] API for programmatic access
- [ ] Site ownership verification (optional)
- [ ] Welsh language support
- [ ] Scottish/NI charity register integration
- [ ] Funder directory (aggregate all funder llms.txt files)

---

## Open Questions

1. **Naming** - `llmstxt-social`? `llmstxt-charity`? `llmstxt-vcse`? Something else?

2. **Hosting model** - If we host files for orgs, how do we handle orgs that go dormant? Auto-expire after X months of no activity?

3. **Bulk pricing** - Infrastructure orgs (CVS, funders) might want to generate for many orgs. Special tier?

4. **Data enrichment** - Should we pull in Charity Commission data to enrich the output? (registered charity name, objects, income band)

5. **Quality threshold** - Do we refuse to generate for sites with insufficient content? Or generate with warnings?

6. **Update notifications** - When we detect site changes, do we notify the org? Auto-regenerate?

7. **Funder uptake** - How do we get funders to adopt? ACF (Association of Charitable Foundations) could be a key partner. Could we offer to generate for all 360Giving publishers as a proof of concept?

8. **Current status field** - For funders, "currently open/closed" is crucial but changes frequently. How do we keep this current? Manual updates? Scrape deadline pages?

9. **Success rate sensitivity** - Many funders won't want to publish success rates. Do we make this optional, or push for transparency?

10. **Matching/recommendations** - If we have both charity and funder llms.txt files, do we build matching features? Or stay focused on generation and let others build on top?

---

## Success Metrics

### Open Source
- GitHub stars
- PyPI downloads
- Community contributions
- Adoption by notable orgs
- Mentions in sector press (Third Sector, Civil Society News)

### Hosted Service
- Sites generated (target: 500 in first 6 months)
- Conversion free → paid
- MRR
- Usage of hosted files (are AI systems actually fetching them?)

### Impact
- Qualitative: Are AI systems representing these orgs more accurately?
- Can we track mentions in AI responses before/after?

---

## Competitive Landscape

- **llmstxt.org tools** - Generic generators, not sector-specific
- **Yoast SEO** - Has llms.txt feature but WordPress only, not VCSE focused
- **Firecrawl llmstxt** - Generic scraping tool
- **No sector-specific solution exists** - Clear gap

---

## Why Social Sector Focus?

1. **Clear need** - These orgs most affected by AI misrepresentation, least able to fix it themselves
2. **Defined audience** - Can market through existing networks (NCVO, local CVS, ACF, etc.)
3. **Domain expertise** - Your consulting background means you understand the nuances
4. **Differentiation** - Generic tools won't handle the specific needs (safeguarding language, service eligibility, funder requirements)
5. **Two-sided market** - Both charities AND funders benefit, creating network effects
6. **Data ecosystem** - Can integrate with existing infrastructure (Charity Commission, 360Giving)
7. **Social value** - Genuinely useful, not just another SaaS
8. **Potential for funding** - Could attract grant funding for free tier sustainability (this is infrastructure for the sector)

---

## Next Steps

1. [ ] Finalise naming
2. [ ] Set up GitHub repo with MIT license
3. [ ] Build proof-of-concept crawler + generator
4. [ ] Test on 5 real sites from your network
5. [ ] Refine prompts based on output quality
6. [ ] Package CLI and publish to PyPI
7. [ ] Build simple hosted version
8. [ ] Soft launch and gather feedback
