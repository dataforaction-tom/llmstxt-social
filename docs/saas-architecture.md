# SaaS Web Platform Architecture Plan

## Overview

Transform llmstxt-social from an open-source CLI into a dual offering:
1. **Open-source CLI** - Continues as free, self-hosted tool
2. **SaaS Web Platform** - Commercial web service built on shared core

**Key Principles:**
- Share all templates and core logic between CLI and web
- Monorepo structure for easy synchronization
- Updates to templates/logic automatically benefit both
- CLI remains 100% functional and open-source

## Business Model

### Free Tier
- Basic llms.txt generation for any URL
- All 4 templates (charity, funder, public_sector, startup)
- No enrichment data
- No quality assessment
- Rate limited: 10 generations/day per IP

### Paid Tier (One-time Payment)
- **Price**: £29 per URL (suggested)
- Everything in Free tier, plus:
  - Charity Commission enrichment
  - 360Giving enrichment for funders
  - Full quality assessment with AI analysis
  - Website gap analysis
  - Size-based recommendations
  - JSON + Markdown downloadable reports
  - Priority processing (no rate limits)
  - Valid for 30 days (can regenerate for same URL)

### Subscription Tier (Future - Phase 2)
- **Price**: £9/month per monitored URL
- Everything in Paid tier, plus:
  - Automatic monitoring (weekly/monthly checks)
  - Auto-regeneration when website changes detected
  - Email notifications to admin on updates
  - Change tracking and history
  - Comparison reports (before/after)
  - Dashboard with all monitored URLs
  - API access for integration

## Repository Structure (Monorepo)

```
llmstxt-social/
├── README.md
├── LICENSE
├── .gitignore
├── docker-compose.yml          # Local development
│
├── packages/
│   ├── core/                   # Shared core library
│   │   ├── pyproject.toml
│   │   ├── src/llmstxt_core/
│   │   │   ├── __init__.py
│   │   │   ├── templates/      # Shared templates
│   │   │   │   ├── charity.py
│   │   │   │   ├── funder.py
│   │   │   │   ├── public_sector.py
│   │   │   │   └── startup.py
│   │   │   ├── crawler.py      # Website crawling
│   │   │   ├── extractor.py    # Content extraction
│   │   │   ├── analyzer.py     # Claude analysis
│   │   │   ├── generator.py    # llms.txt generation
│   │   │   ├── validator.py    # Validation
│   │   │   ├── assessor.py     # Quality assessment
│   │   │   └── enrichers/      # Data enrichment
│   │   │       ├── charity_commission.py
│   │   │       └── threesixty_giving.py
│   │   └── tests/
│   │
│   ├── cli/                    # Open-source CLI
│   │   ├── pyproject.toml
│   │   ├── src/llmstxt_social/
│   │   │   ├── __init__.py
│   │   │   └── cli.py          # CLI interface only
│   │   ├── tests/
│   │   └── README.md
│   │
│   ├── api/                    # FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── src/llmstxt_api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py         # FastAPI app
│   │   │   ├── config.py       # Settings
│   │   │   ├── database.py     # DB connection
│   │   │   ├── models.py       # SQLAlchemy models
│   │   │   ├── schemas.py      # Pydantic schemas
│   │   │   ├── routes/
│   │   │   │   ├── generate.py # Generation endpoints
│   │   │   │   ├── assess.py   # Assessment endpoints
│   │   │   │   ├── payment.py  # Stripe integration
│   │   │   │   └── monitor.py  # Subscription monitoring
│   │   │   ├── services/
│   │   │   │   ├── generation.py
│   │   │   │   ├── assessment.py
│   │   │   │   ├── payment.py
│   │   │   │   └── monitoring.py
│   │   │   └── tasks/          # Background jobs
│   │   │       ├── celery.py
│   │   │       └── monitor.py
│   │   ├── alembic/            # Database migrations
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   └── web/                    # React frontend
│       ├── package.json
│       ├── src/
│       │   ├── App.tsx
│       │   ├── pages/
│       │   │   ├── Home.tsx
│       │   │   ├── Generate.tsx
│       │   │   ├── Assess.tsx
│       │   │   ├── Dashboard.tsx
│       │   │   └── Pricing.tsx
│       │   ├── components/
│       │   │   ├── GenerationForm.tsx
│       │   │   ├── TemplateSelector.tsx
│       │   │   ├── AssessmentReport.tsx
│       │   │   └── PaymentFlow.tsx
│       │   ├── api/
│       │   │   └── client.ts
│       │   └── types/
│       ├── public/
│       ├── tests/
│       └── Dockerfile
│
├── infrastructure/             # Deployment configs
│   ├── digitalocean/
│   │   └── app.yaml           # DigitalOcean App Platform config
│   └── nginx/
│
└── docs/
    ├── saas-architecture.md   # This file
    ├── api.md
    └── deployment.md
```

## Architecture Design

### Core Library (`packages/core`)

**Purpose**: Shared business logic used by both CLI and API

**Key Components:**
- Templates (charity, funder, public_sector, startup)
- Generation pipeline (crawl → extract → analyze → generate)
- Assessment engine (rule-based + AI quality analysis)
- Enrichment integrations (Charity Commission, 360Giving)
- All PageType definitions and data models

**Installation:**
```python
# In CLI
pip install -e ../core

# In API
pip install -e ../core
```

**Benefits:**
- Single source of truth for templates
- Updates propagate to both CLI and web instantly
- Easier testing and maintenance
- Can publish as standalone package later

### CLI Package (`packages/cli`)

**Purpose**: Open-source command-line interface

**Changes from Current:**
- Thin wrapper around `llmstxt_core`
- CLI-specific code only (Typer commands, Rich UI)
- Imports all logic from core package

**Remains:**
- Fully functional standalone
- Same commands (generate, assess, validate, preview)
- Same features and quality
- MIT licensed, completely open

### API Backend (`packages/api`)

**Tech Stack:**
- **Framework**: FastAPI (async, fast, auto-docs)
- **Database**: PostgreSQL (user data, jobs, payments)
- **Cache**: Redis (rate limiting, session storage)
- **Queue**: Celery + Redis (background jobs for long-running tasks)
- **Storage**: DigitalOcean Spaces (generated files, reports)
- **Auth**: JWT tokens
- **Payments**: Stripe
- **Email**: Resend

**Database Schema:**

```sql
-- Users (optional, can do email-only for MVP)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    stripe_customer_id VARCHAR(255)
);

-- Generation jobs
CREATE TABLE generation_jobs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    url VARCHAR(2048) NOT NULL,
    template VARCHAR(50) NOT NULL,
    tier VARCHAR(20) NOT NULL, -- 'free', 'paid', 'subscription'
    status VARCHAR(20) NOT NULL, -- 'pending', 'processing', 'completed', 'failed'

    -- Output
    llmstxt_content TEXT,
    assessment_json JSONB,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,

    -- Billing
    payment_intent_id VARCHAR(255),
    amount_paid INTEGER,

    INDEX (user_id, created_at),
    INDEX (url, expires_at)
);

-- Monitoring subscriptions (Phase 2)
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    url VARCHAR(2048) NOT NULL,
    template VARCHAR(50) NOT NULL,
    frequency VARCHAR(20) NOT NULL, -- 'weekly', 'monthly'

    active BOOLEAN DEFAULT TRUE,
    last_check TIMESTAMP,
    last_change_detected TIMESTAMP,

    -- Stripe
    stripe_subscription_id VARCHAR(255),

    created_at TIMESTAMP DEFAULT NOW(),
    cancelled_at TIMESTAMP
);

-- Monitoring history (Phase 2)
CREATE TABLE monitoring_history (
    id UUID PRIMARY KEY,
    subscription_id UUID REFERENCES subscriptions(id),
    checked_at TIMESTAMP DEFAULT NOW(),
    changed BOOLEAN DEFAULT FALSE,
    llmstxt_content TEXT,
    assessment_json JSONB,
    notification_sent BOOLEAN DEFAULT FALSE
);
```

**API Endpoints:**

```
POST   /api/generate/free
  Body: { url, template }
  Returns: { job_id, status, llmstxt_content }

POST   /api/generate/paid
  Body: { url, template, payment_intent_id }
  Returns: { job_id, status, llmstxt_content, assessment }

GET    /api/generate/{job_id}
  Returns: { status, llmstxt_content, assessment, ... }

POST   /api/assess
  Body: { url or file_content, template }
  Returns: { assessment_json }

POST   /api/payment/create-intent
  Body: { url, template }
  Returns: { client_secret, amount }

POST   /api/payment/webhook
  Stripe webhook handler

# Phase 2: Subscriptions
POST   /api/subscriptions
POST   /api/subscriptions/{id}/cancel
GET    /api/subscriptions/{id}/history
```

**Background Job Architecture:**

Use Celery for long-running tasks:

```python
# tasks/generate.py
@celery_app.task
async def generate_llmstxt_task(job_id: str, url: str, template: str, tier: str):
    """Background task for generation."""
    job = await db.get_job(job_id)

    try:
        # Update status
        await db.update_job(job_id, status='processing')

        # Use core library
        from llmstxt_core.crawler import crawl_site
        from llmstxt_core.extractor import extract_content
        from llmstxt_core.analyzer import analyze_organisation
        from llmstxt_core.generator import generate_llmstxt

        # Crawl
        crawl_result = await crawl_site(url, max_pages=30)

        # Extract
        pages = [extract_content(p) for p in crawl_result.pages]

        # Analyze
        analysis = await analyze_organisation(pages, template)

        # Generate
        llmstxt_content = generate_llmstxt(analysis, pages, template)

        # If paid tier, do enrichment + assessment
        if tier in ['paid', 'subscription']:
            from llmstxt_core.enrichers import fetch_charity_data
            from llmstxt_core.assessor import LLMSTxtAssessor

            # Enrichment
            charity_data = await fetch_charity_data(...)

            # Assessment
            assessor = LLMSTxtAssessor(template, anthropic_client)
            assessment = await assessor.assess(
                llmstxt_content,
                website_url=url,
                crawl_result=crawl_result,
                enrichment_data=charity_data
            )

            await db.update_job(
                job_id,
                status='completed',
                llmstxt_content=llmstxt_content,
                assessment_json=assessment.to_dict()
            )
        else:
            await db.update_job(
                job_id,
                status='completed',
                llmstxt_content=llmstxt_content
            )

    except Exception as e:
        await db.update_job(job_id, status='failed', error=str(e))
        raise
```

**Rate Limiting:**

```python
# middleware/rate_limit.py
from fastapi import Request, HTTPException
from redis import Redis

redis_client = Redis()

async def rate_limit_free_tier(request: Request):
    """Limit free tier to 10 requests per day per IP."""
    ip = request.client.host
    key = f"rate_limit:free:{ip}:{date.today()}"

    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, 86400)  # 24 hours

    if count > 10:
        raise HTTPException(
            status_code=429,
            detail="Free tier limit reached. Upgrade to paid tier."
        )
```

### Web Frontend (`packages/web`)

**Tech Stack:**
- React 18+ with TypeScript
- Vite (build tool)
- TanStack Query (data fetching)
- Tailwind CSS (styling)
- Stripe Elements (payment UI)
- React Router (routing)

**Key Pages:**

1. **Home Page** (`/`)
   - Hero section explaining llms.txt
   - Quick "Try it free" form
   - Example outputs
   - Pricing comparison table

2. **Generate Page** (`/generate`)
   - URL input
   - Template selector (4 templates)
   - Free vs Paid toggle
   - Real-time progress updates (WebSocket or polling)
   - Download buttons (text, JSON, Markdown)

3. **Assessment Page** (`/assess`)
   - Upload or paste llms.txt content
   - OR enter URL for live assessment
   - Visual assessment report with scores
   - Color-coded recommendations
   - Comparison with website analysis

4. **Pricing Page** (`/pricing`)
   - Three tiers: Free, Paid, Subscription
   - Feature comparison table
   - FAQs

5. **Dashboard** (`/dashboard`) - Phase 2
   - List of monitored URLs
   - Status indicators
   - Recent assessments
   - Change history

**Payment Flow:**

```typescript
// Payment flow for one-time purchase
const handlePaidGeneration = async () => {
  // 1. Create payment intent
  const { clientSecret, amount } = await api.createPaymentIntent({
    url,
    template
  });

  // 2. Show Stripe payment form
  const { paymentIntent } = await stripe.confirmPayment({
    clientSecret,
    confirmParams: { /* ... */ }
  });

  // 3. Submit generation job with payment proof
  const job = await api.generatePaid({
    url,
    template,
    paymentIntentId: paymentIntent.id
  });

  // 4. Poll for completion
  const result = await pollJobStatus(job.id);

  // 5. Download results
  downloadLLMSTxt(result.llmstxt_content);
  downloadAssessment(result.assessment);
};
```

**Real-time Updates:**

Use Server-Sent Events (SSE) for progress updates:

```typescript
const useGenerationProgress = (jobId: string) => {
  const [progress, setProgress] = useState<Progress>({ status: 'pending' });

  useEffect(() => {
    const eventSource = new EventSource(`/api/jobs/${jobId}/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);

      if (data.status === 'completed' || data.status === 'failed') {
        eventSource.close();
      }
    };

    return () => eventSource.close();
  }, [jobId]);

  return progress;
};
```

## Stripe Integration

### One-time Payment (Paid Tier)

```python
# services/payment.py
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_payment_intent(url: str, template: str):
    """Create Stripe payment intent for one-time purchase."""

    # Calculate price (could vary by template)
    amount = 2900  # £29.00 in pence

    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency='gbp',
        metadata={
            'url': url,
            'template': template,
            'tier': 'paid'
        },
        automatic_payment_methods={'enabled': True}
    )

    return {
        'client_secret': intent.client_secret,
        'amount': amount
    }

async def handle_webhook(payload: bytes, sig_header: str):
    """Handle Stripe webhook events."""

    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object

        # Create generation job
        job = await create_generation_job(
            url=payment_intent.metadata['url'],
            template=payment_intent.metadata['template'],
            tier='paid',
            payment_intent_id=payment_intent.id,
            amount_paid=payment_intent.amount
        )

        # Trigger background task
        generate_llmstxt_task.delay(job.id, ...)
```

### Subscription (Phase 2)

```python
async def create_subscription(user_id: str, url: str, template: str, frequency: str):
    """Create monitoring subscription."""

    # Create Stripe subscription
    subscription = stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[{
            'price': settings.STRIPE_MONITORING_PRICE_ID,
        }],
        metadata={
            'url': url,
            'template': template,
            'frequency': frequency
        }
    )

    # Store in DB
    await db.create_subscription(
        user_id=user_id,
        url=url,
        template=template,
        frequency=frequency,
        stripe_subscription_id=subscription.id
    )
```

## Email Service (Resend Integration)

### Configuration

```python
# services/email.py
import resend

resend.api_key = settings.RESEND_API_KEY

async def send_email(
    to: str,
    subject: str,
    html: str,
    from_email: str = "llmstxt <notifications@llmstxt.io>"
):
    """Send email via Resend."""

    params = {
        "from": from_email,
        "to": [to],
        "subject": subject,
        "html": html
    }

    email = resend.Emails.send(params)
    return email
```

### Change Notification Email (Phase 2)

```python
async def send_change_notification(sub, new_content, old_content):
    """Send email notification about changes."""

    from llmstxt_core.assessor import LLMSTxtAssessor

    # Run assessment on new version
    assessor = LLMSTxtAssessor(sub.template)
    assessment = await assessor.assess(new_content)

    # Generate comparison
    diff = generate_diff(old_content, new_content)

    # Render HTML template
    html = render_template(
        "change_notification.html",
        url=sub.url,
        diff=diff,
        assessment=assessment,
        dashboard_link=f"{settings.BASE_URL}/dashboard"
    )

    # Send via Resend
    await send_email(
        to=sub.user.email,
        subject=f"llms.txt updated for {sub.url}",
        html=html
    )
```

### Email Templates

```html
<!-- templates/change_notification.html -->
<!DOCTYPE html>
<html>
<head>
    <style>
        .diff-added { background: #e6ffed; }
        .diff-removed { background: #ffeef0; }
        .score { font-size: 24px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Your llms.txt has been updated</h1>

    <p>We've detected changes on <strong>{{ url }}</strong> and regenerated your llms.txt file.</p>

    <h2>Quality Score</h2>
    <div class="score">{{ assessment.overall_score }}/100</div>

    <h2>What Changed</h2>
    <pre>{{ diff }}</pre>

    <h2>Top Recommendations</h2>
    <ul>
    {% for rec in assessment.recommendations %}
        <li>{{ rec }}</li>
    {% endfor %}
    </ul>

    <p>
        <a href="{{ dashboard_link }}">View in Dashboard</a>
    </p>
</body>
</html>
```

## Monitoring Service (Phase 2)

### Architecture

```python
# tasks/monitor.py
from celery import Celery
from celery.schedules import crontab

celery_app = Celery('llmstxt_monitor')

# Schedule daily check task
celery_app.conf.beat_schedule = {
    'check-subscriptions': {
        'task': 'tasks.monitor.check_all_subscriptions',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}

@celery_app.task
async def check_all_subscriptions():
    """Check all active subscriptions."""
    subscriptions = await db.get_due_subscriptions()

    for sub in subscriptions:
        check_subscription_task.delay(sub.id)

@celery_app.task
async def check_subscription_task(subscription_id: str):
    """Check a single subscription for changes."""

    sub = await db.get_subscription(subscription_id)

    # Generate new llms.txt
    from llmstxt_core import (
        crawl_site, extract_content,
        analyze_organisation, generate_llmstxt
    )

    crawl_result = await crawl_site(sub.url, max_pages=30)
    pages = [extract_content(p) for p in crawl_result.pages]
    analysis = await analyze_organisation(pages, sub.template)
    new_content = generate_llmstxt(analysis, pages, sub.template)

    # Get previous content
    last_history = await db.get_latest_history(subscription_id)
    previous_content = last_history.llmstxt_content if last_history else None

    # Detect changes
    changed = previous_content != new_content

    # Save history
    await db.create_history(
        subscription_id=subscription_id,
        llmstxt_content=new_content,
        changed=changed
    )

    # If changed, send notification
    if changed:
        await send_change_notification(sub, new_content, previous_content)
```

## Deployment Architecture (DigitalOcean)

### DigitalOcean App Platform Configuration

**Why DigitalOcean:**
- UK/EU data centers available (data residency)
- Managed PostgreSQL and Redis
- Auto-scaling and load balancing
- GitHub integration for auto-deploy
- Competitive pricing
- Spaces (S3-compatible) for file storage

**App Platform Structure:**

```yaml
# infrastructure/digitalocean/app.yaml
name: llmstxt-social
region: lon  # London datacenter

databases:
  - name: llmstxt-db
    engine: PG
    version: "15"
    size: db-s-1vcpu-2gb
    num_nodes: 1

  - name: llmstxt-redis
    engine: REDIS
    version: "7"
    size: db-s-1vcpu-1gb

services:
  # FastAPI Backend
  - name: api
    github:
      repo: yourusername/llmstxt-social
      branch: main
      deploy_on_push: true
    source_dir: /packages/api
    dockerfile_path: packages/api/Dockerfile

    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: REDIS_URL
        scope: RUN_TIME
        type: SECRET
      - key: ANTHROPIC_API_KEY
        scope: RUN_TIME
        type: SECRET
      - key: STRIPE_SECRET_KEY
        scope: RUN_TIME
        type: SECRET
      - key: STRIPE_WEBHOOK_SECRET
        scope: RUN_TIME
        type: SECRET
      - key: RESEND_API_KEY
        scope: RUN_TIME
        type: SECRET
      - key: SPACES_ACCESS_KEY
        scope: RUN_TIME
        type: SECRET
      - key: SPACES_SECRET_KEY
        scope: RUN_TIME
        type: SECRET
      - key: SPACES_BUCKET
        value: llmstxt-reports
      - key: SPACES_REGION
        value: lon1

    instance_count: 2
    instance_size_slug: professional-xs
    http_port: 8000

    health_check:
      http_path: /health

  # Celery Worker
  - name: celery-worker
    github:
      repo: yourusername/llmstxt-social
      branch: main
    source_dir: /packages/api
    dockerfile_path: packages/api/Dockerfile
    run_command: celery -A llmstxt_api.tasks worker -l info

    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: REDIS_URL
        scope: RUN_TIME
        type: SECRET
      - key: ANTHROPIC_API_KEY
        scope: RUN_TIME
        type: SECRET

    instance_count: 2
    instance_size_slug: professional-s

  # Celery Beat Scheduler
  - name: celery-beat
    github:
      repo: yourusername/llmstxt-social
      branch: main
    source_dir: /packages/api
    dockerfile_path: packages/api/Dockerfile
    run_command: celery -A llmstxt_api.tasks beat -l info

    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: REDIS_URL
        scope: RUN_TIME
        type: SECRET

    instance_count: 1
    instance_size_slug: basic-xxs

  # React Frontend
  - name: web
    github:
      repo: yourusername/llmstxt-social
      branch: main
    source_dir: /packages/web
    dockerfile_path: packages/web/Dockerfile

    envs:
      - key: VITE_API_URL
        value: https://api-llmstxt-social.ondigitalocean.app
      - key: VITE_STRIPE_PUBLIC_KEY
        scope: RUN_TIME
        type: SECRET

    instance_count: 1
    instance_size_slug: basic-xxs
    http_port: 3000

    routes:
      - path: /

# DigitalOcean Spaces for file storage
static_sites:
  - name: reports-cdn
    catchall_document: index.html
    cors:
      - allowed_origins:
          - prefix: https://llmstxt.io
```

### Production Stack

```yaml
# docker-compose.yml (for local dev)
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: llmstxt
      POSTGRES_PASSWORD: dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./packages/api
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:dev_password@postgres/llmstxt
      REDIS_URL: redis://redis:6379
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
      RESEND_API_KEY: ${RESEND_API_KEY}
    ports:
      - "8000:8000"
    volumes:
      - ./packages/core:/app/core
      - ./packages/api:/app/api

  celery_worker:
    build: ./packages/api
    command: celery -A llmstxt_api.tasks worker -l info
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:dev_password@postgres/llmstxt
      REDIS_URL: redis://redis:6379
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}

  celery_beat:
    build: ./packages/api
    command: celery -A llmstxt_api.tasks beat -l info
    depends_on:
      - postgres
      - redis

  web:
    build: ./packages/web
    ports:
      - "3000:3000"
    environment:
      VITE_API_URL: http://localhost:8000
      VITE_STRIPE_PUBLIC_KEY: ${STRIPE_PUBLIC_KEY}

volumes:
  postgres_data:
```

### Infrastructure Needs

- **API**: 2-4 CPU, 4-8GB RAM (for Celery workers)
- **PostgreSQL**: 2GB RAM minimum (DigitalOcean managed DB)
- **Redis**: 1GB RAM (DigitalOcean managed Redis)
- **Storage**: DigitalOcean Spaces (S3-compatible) for reports
- **CDN**: Cloudflare (free tier fine, or DigitalOcean CDN)

### Environment Variables

```bash
# .env.production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

ANTHROPIC_API_KEY=sk-ant-...
CHARITY_COMMISSION_API_KEY=...

STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_MONITORING_PRICE_ID=price_...

# DigitalOcean Spaces (S3-compatible)
SPACES_ACCESS_KEY=...
SPACES_SECRET_KEY=...
SPACES_BUCKET=llmstxt-reports
SPACES_REGION=lon1
SPACES_ENDPOINT=https://lon1.digitaloceanspaces.com

# Resend Email
RESEND_API_KEY=re_...
FROM_EMAIL=notifications@llmstxt.io

BASE_URL=https://llmstxt.io
```

### DigitalOcean Spaces Setup

```python
# services/storage.py
import boto3
from botocore.client import Config

# DigitalOcean Spaces uses S3-compatible API
s3_client = boto3.client(
    's3',
    region_name=settings.SPACES_REGION,
    endpoint_url=settings.SPACES_ENDPOINT,
    aws_access_key_id=settings.SPACES_ACCESS_KEY,
    aws_secret_access_key=settings.SPACES_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

async def upload_report(job_id: str, content: str, format: str):
    """Upload assessment report to Spaces."""

    key = f"reports/{job_id}/assessment.{format}"

    s3_client.put_object(
        Bucket=settings.SPACES_BUCKET,
        Key=key,
        Body=content.encode('utf-8'),
        ContentType='text/markdown' if format == 'md' else 'application/json',
        ACL='private'
    )

    # Generate signed URL (valid for 7 days)
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.SPACES_BUCKET,
            'Key': key
        },
        ExpiresIn=604800  # 7 days
    )

    return url
```

## Migration Strategy

### Phase 1: Extract Core Library

1. Create `packages/core` directory
2. Move all business logic from `src/llmstxt_social/` to `packages/core/src/llmstxt_core/`
3. Keep only CLI interface code in `packages/cli/src/llmstxt_social/cli.py`
4. Update imports in CLI to use `llmstxt_core`
5. Test CLI works identically
6. Update README to explain monorepo structure

### Phase 2: Build API (MVP)

1. Create FastAPI project structure
2. Implement basic endpoints:
   - POST /generate/free (no auth, rate limited)
   - POST /generate/paid (with Stripe)
   - GET /jobs/{id}
3. Add PostgreSQL schema
4. Integrate Celery for background jobs
5. Set up DigitalOcean App Platform
6. Configure Resend for emails
7. Deploy to DigitalOcean

### Phase 3: Build Web Frontend (MVP)

1. Create React app with Vite
2. Build core pages (Home, Generate, Pricing)
3. Implement payment flow with Stripe Elements
4. Add progress tracking for jobs
5. Deploy to DigitalOcean App Platform (or Vercel/Netlify)

### Phase 4: Subscription Monitoring (Future)

1. Extend database schema for subscriptions
2. Add subscription endpoints
3. Implement Celery beat for scheduled checks
4. Build dashboard UI
5. Set up email notifications via Resend

## Pricing Recommendations

### Free Tier
- **Cost**: £0
- **Limit**: 10 generations/day per IP
- **Features**: Basic generation only

### Paid Tier (One-time)
- **Cost**: £29 per URL
- **Valid**: 30 days (can regenerate for same URL)
- **Features**: Full enrichment + assessment
- **Target**: Organizations wanting a one-time audit

### Subscription
- **Cost**: £9/month per URL
- **Features**: Auto-monitoring + regeneration + history
- **Target**: Organizations wanting ongoing maintenance
- **Discount**: £99/year (save 8%)

### Volume Discounts (Future)
- 5+ URLs: 10% off
- 10+ URLs: 20% off
- Enterprise (20+): Custom pricing

## Marketing & Launch

### Target Audiences

1. **Charity sector organizations** - Primary market
2. **Funders and foundations** - High value customers
3. **Consultancy firms** - Agencies serving charities
4. **Local authorities** - Public sector bodies
5. **Social enterprises** - Smaller but growing market

### Launch Strategy

1. **Beta Phase** (Month 1)
   - Free tier only
   - Gather feedback
   - Build case studies
   - 100 free generations to first users

2. **Paid Launch** (Month 2)
   - Introduce paid tier
   - Launch with discount: £19 instead of £29
   - Target early adopters

3. **Growth Phase** (Month 3+)
   - Add subscription tier
   - Content marketing (blog posts, examples)
   - Partnerships with charity sector orgs
   - Conference presence (NCVO, CharityComms)

### SEO/Content Strategy

- Blog: "How to create an llms.txt file for your charity"
- Examples: Public directory of good llms.txt files
- Tools: Free validator (no generation)
- Case studies: Before/after improvements

## Technical Debt & Considerations

### Security
- Rate limiting on all endpoints
- Input validation (URL allowlists?)
- Stripe webhook signature verification
- SQL injection prevention (use ORMs)
- XSS prevention in frontend
- CORS configuration

### Performance
- Caching common templates
- CDN for static assets (DigitalOcean CDN or Cloudflare)
- Database indexing on hot paths
- Connection pooling
- Celery queue monitoring

### Monitoring
- Sentry for error tracking
- DigitalOcean monitoring and alerts
- Stripe dashboard for payments
- Database query performance monitoring

### Legal/Compliance
- GDPR compliance (EU users)
- Privacy policy
- Terms of service
- Cookie consent
- Data retention policy
- VAT handling (if selling in EU)

## Success Metrics

### MVP Launch Goals (3 months)
- 500 free generations
- 20 paid conversions
- £580 revenue
- <5% error rate
- <1% refund rate

### Growth Goals (6 months)
- 2000 free generations/month
- 100 paid conversions/month
- 20 active subscriptions
- £4000 MRR
- Build case study library

### Long-term Goals (12 months)
- 5000 free generations/month
- 200 paid conversions/month
- 100 active subscriptions
- £10,000 MRR
- Enterprise clients
- API access tier

## Next Steps

To build this:

1. **Week 1-2: Monorepo Refactor**
   - Extract core library
   - Update CLI to use core
   - Test everything still works
   - Update documentation

2. **Week 3-4: API MVP**
   - FastAPI project setup
   - Database schema
   - Free tier endpoint
   - Paid tier endpoint with Stripe
   - Celery background jobs
   - Deploy to DigitalOcean App Platform

3. **Week 5-6: Web MVP**
   - React app setup
   - Home + Generate pages
   - Stripe integration
   - Progress tracking
   - Deploy to DigitalOcean or Vercel

4. **Week 7-8: Beta Launch**
   - Testing with real users
   - Bug fixes
   - Performance tuning
   - Documentation

5. **Week 9+: Iterate**
   - Add features based on feedback
   - Marketing push
   - Subscription tier (Phase 2)

## Files to Create/Modify

### Immediate (Monorepo Setup)
- Create `packages/core/` structure
- Move files from `src/llmstxt_social/` to `packages/core/src/llmstxt_core/`
- Update `packages/cli/pyproject.toml` to depend on core
- Create root `README.md` explaining monorepo
- Add `docker-compose.yml` for development

### API (Phase 2)
- `packages/api/src/llmstxt_api/main.py`
- `packages/api/src/llmstxt_api/routes/` (all route files)
- `packages/api/src/llmstxt_api/services/` (all service files)
- `packages/api/src/llmstxt_api/models.py`
- `packages/api/alembic/` (migration files)

### Web (Phase 3)
- `packages/web/src/` (all React components)
- `packages/web/src/api/client.ts`
- `packages/web/src/pages/` (all page components)

### Documentation
- `docs/saas-architecture.md` (this file)
- `docs/api.md` (API documentation)
- `docs/deployment.md` (deployment guide)
- Updated root `README.md`

### Infrastructure
- `infrastructure/digitalocean/app.yaml`
- `packages/api/Dockerfile`
- `packages/web/Dockerfile`

## Risk Mitigation

### Technical Risks
- **Claude API costs**: Monitor usage, implement caching, offer cheaper models for free tier
- **Crawling failures**: Implement retry logic, fallback strategies, clear error messages
- **Database performance**: Index properly, use read replicas if needed, cache aggressively

### Business Risks
- **Low conversion rate**: Offer trials, reduce price, improve value proposition
- **High support burden**: Good documentation, FAQs, automated responses
- **Competition**: Focus on UK charity sector specialization, superior templates

### Operational Risks
- **Stripe issues**: Test thoroughly, handle webhooks carefully, monitor transactions
- **Email deliverability**: Use Resend's verified domain, monitor bounce rates, warm up sending
- **Downtime**: Use DigitalOcean managed services, set up monitoring and alerts, have backup plan

## Cost Estimates

### Monthly Operating Costs (MVP)

**DigitalOcean:**
- App Platform (API + Workers): ~$24/month
- Managed PostgreSQL (2GB): ~$15/month
- Managed Redis (1GB): ~$15/month
- Spaces (100GB storage): ~$5/month
- **Total Infrastructure**: ~$59/month

**Third-party Services:**
- Resend (10k emails/month): $0 (free tier)
- Stripe fees: ~2.4% + 20p per transaction
- Anthropic API: Variable (free tier for testing)
- Domain + SSL: ~$15/year
- **Total Services**: ~$1/month + API costs

**Break-even Analysis:**
- Fixed costs: ~£60/month
- Need: 3 paid conversions/month to break even
- Target: 10+ paid conversions/month for profitability

### Scaling Costs (Phase 2+)

At 100 paid conversions/month:
- Infrastructure: ~£150/month (more workers, bigger DB)
- Resend: ~£20/month (50k emails)
- Anthropic: ~£300/month (Claude API usage)
- **Total**: ~£470/month
- **Revenue**: £2,900/month
- **Profit Margin**: ~84%
