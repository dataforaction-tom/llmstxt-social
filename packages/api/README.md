# llmstxt-api

FastAPI backend for the llmstxt SaaS platform.

## Features

- **Free tier**: Basic llms.txt generation with rate limiting
- **Paid tier**: Full generation with enrichment, assessment, and reports
- **Background jobs**: Celery integration for long-running tasks
- **Payments**: Stripe integration for one-time and subscription payments
- **Email**: Resend integration for notifications

## Installation

```bash
cd packages/api
pip install -e .
```

## Development

### Environment Setup

Create a `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:dev_password@localhost:5432/llmstxt

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
CHARITY_COMMISSION_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Resend
RESEND_API_KEY=re_...

# App Settings
SECRET_KEY=your-secret-key-here
BASE_URL=http://localhost:8000
```

### Start Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start API server
uvicorn llmstxt_api.main:app --reload

# Start Celery worker (in another terminal)
celery -A llmstxt_api.tasks.celery worker -l info

# Start Celery beat (for scheduled tasks)
celery -A llmstxt_api.tasks.celery beat -l info
```

## API Endpoints

- `GET /` - API info and health check
- `POST /api/generate/free` - Free tier generation
- `POST /api/generate/paid` - Paid tier with assessment
- `GET /api/jobs/{job_id}` - Get job status and results
- `POST /api/payment/create-intent` - Create Stripe payment
- `POST /api/payment/webhook` - Stripe webhook handler

## Testing

```bash
pytest
```

## License

MIT
