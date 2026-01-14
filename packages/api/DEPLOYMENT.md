# API Deployment Guide

## Local Development

### 1. Set up environment

```bash
# Copy environment template
cd packages/api
cp .env.example .env

# Edit .env with your actual keys
# Required: ANTHROPIC_API_KEY
# Optional: STRIPE_SECRET_KEY, RESEND_API_KEY, CHARITY_COMMISSION_API_KEY
```

### 2. Start services with Docker Compose

```bash
# From repository root
docker-compose up -d postgres redis
```

### 3. Run database migrations

```bash
cd packages/api
alembic upgrade head
```

### 4. Start the API

```bash
# Development server with auto-reload
uvicorn llmstxt_api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start Celery worker (in separate terminal)

```bash
celery -A llmstxt_api.tasks.celery worker -l info
```

### 6. Access the API

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Running with Docker Compose

```bash
# Start all services (API + Worker + DB + Redis)
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery_worker

# Stop all services
docker-compose down
```

## Testing the API

### Health Check

```bash
curl http://localhost:8000/health
```

### Generate llms.txt (Free Tier)

```bash
curl -X POST "http://localhost:8000/api/generate/free" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example-charity.org.uk",
    "template": "charity"
  }'
```

### Check Job Status

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

## Production Deployment (DigitalOcean App Platform)

### 1. Prepare Repository

Ensure your `.gitignore` excludes:
- `.env` files
- `__pycache__`
- `.pytest_cache`
- `*.pyc`

### 2. Set up DigitalOcean Resources

**Database:**
- Create Managed PostgreSQL database (2GB RAM minimum)
- Note the connection string

**Redis:**
- Create Managed Redis (1GB RAM minimum)
- Note the connection string

**Spaces:**
- Create a Space for file storage (optional for reports)

### 3. Configure App Platform

Create `infrastructure/digitalocean/app.yaml` or use web UI:

**Components:**
1. **API Service**
   - Source: GitHub repo, `packages/api` directory
   - Dockerfile path: `packages/api/Dockerfile`
   - Instance: Professional XS (2 CPU, 2GB RAM)
   - Port: 8000
   - Health check: `/health`

2. **Celery Worker**
   - Source: Same repo
   - Dockerfile path: `packages/api/Dockerfile`
   - Command: `celery -A llmstxt_api.tasks.celery worker -l info`
   - Instance: Professional S (4GB RAM)

3. **Environment Variables:**
   ```
   DATABASE_URL=${database.DATABASE_URL}
   REDIS_URL=${redis.REDIS_URL}
   ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
   STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
   STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
   RESEND_API_KEY=${RESEND_API_KEY}
   SECRET_KEY=${SECRET_KEY}
   BASE_URL=https://api.llmstxt.io
   ENVIRONMENT=production
   ```

### 4. Deploy

```bash
# Push to main branch
git push origin main

# DigitalOcean will auto-deploy
```

### 5. Run Migrations

After first deployment:

```bash
# Connect to API container
doctl apps exec {app-id} --component api

# Run migrations
cd /app/api && alembic upgrade head
```

### 6. Configure Stripe Webhooks

- Go to Stripe Dashboard → Webhooks
- Add endpoint: `https://api.llmstxt.io/api/payment/webhook`
- Select events: `payment_intent.succeeded`, `payment_intent.payment_failed`
- Copy webhook secret to environment variables

## Monitoring

### Logs

```bash
# DigitalOcean
doctl apps logs {app-id} --component api --follow
doctl apps logs {app-id} --component celery_worker --follow

# Docker Compose
docker-compose logs -f api celery_worker
```

### Health Checks

```bash
# API health
curl https://api.llmstxt.io/health

# Database connectivity (checks in startup)
# Redis connectivity (rate limiting will fail if Redis down)
```

### Metrics to Monitor

- Request latency
- Error rate
- Job completion rate
- Queue length (Celery)
- Database connections
- Redis memory usage

## Troubleshooting

### API won't start

Check:
1. Database connection string correct
2. Redis URL correct
3. All required environment variables set
4. Migrations have been run

### Jobs stuck in "pending"

Check:
1. Celery worker is running
2. Redis is accessible
3. Worker logs for errors

### Rate limiting not working

Check:
1. Redis connection
2. Middleware is enabled in main.py

### Payments not processing

Check:
1. Stripe webhook is configured
2. Webhook secret matches environment variable
3. Payment endpoint logs

## Scaling

### Horizontal Scaling

- **API**: Scale to 2-4 instances with load balancer
- **Workers**: Scale to 2-4 workers for concurrent job processing

### Database Scaling

- Enable connection pooling (already configured)
- Add read replicas for read-heavy workloads
- Consider caching frequently accessed data

### Redis Scaling

- Monitor memory usage
- Increase size if rate limiting data grows
- Consider Redis Cluster for high availability

## Security Checklist

- [ ] Change SECRET_KEY from default
- [ ] Use strong database password
- [ ] Enable SSL for database connections
- [ ] Configure CORS for production domain only
- [ ] Enable HTTPS (automatic with DigitalOcean App Platform)
- [ ] Rotate API keys regularly
- [ ] Set up monitoring and alerts
- [ ] Regular security updates
