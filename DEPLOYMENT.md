# Deployment Guide

This guide covers deploying the llmstxt-social SaaS platform (API + Web frontend + Background workers).

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Single-VM Docker (Recommended)](#single-vm-docker-recommended)
- [Railway Deployment](#railway-deployment)
- [DigitalOcean Deployment](#digitalocean-deployment)
- [Self-Hosted VPS](#self-hosted-vps)
- [Environment Variables](#environment-variables)
- [Post-Deployment](#post-deployment)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

This is a monorepo with the following services:

```
┌─────────────────────────────────────────────────────────────┐
│                        Services                              │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Web (React)   │   API (FastAPI) │   Worker (Celery)       │
│   Port 3000     │   Port 8000     │   Background Jobs       │
└────────┬────────┴────────┬────────┴────────────┬────────────┘
         │                 │                      │
         │                 ▼                      │
         │         ┌──────────────┐               │
         │         │  PostgreSQL  │◄──────────────┤
         │         │  Port 5432   │               │
         │         └──────────────┘               │
         │                                        │
         │         ┌──────────────┐               │
         └────────►│    Redis     │◄──────────────┘
                   │  Port 6379   │
                   └──────────────┘
```

**Services to deploy:**
1. **PostgreSQL** - Primary database
2. **Redis** - Job queue and caching
3. **API** - FastAPI backend (`packages/api/Dockerfile`)
4. **Worker** - Celery background processor (same Dockerfile, different command)
5. **Web** - React frontend (`packages/web/Dockerfile`)

## Prerequisites

### Required

- **Anthropic API Key** - Get from https://console.anthropic.com/

### Optional (for paid tier)

- **Stripe Account** - Get keys from https://dashboard.stripe.com/
- **Resend API Key** - For email notifications (https://resend.com/)
- **Charity Commission API Key** - For UK charity enrichment

## Local Development

### 1. Clone and Setup

```bash
git clone https://github.com/dataforaction-tom/llmstxt-social.git
cd llmstxt-social
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start the Full Stack

```bash
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### 3. Access the Application

- **Web Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health

---

## Single-VM Docker (Recommended)

This is the simplest reliable production setup: one VM running all services
(API + web UI + worker + beat + Postgres + Redis) via Docker Compose.

### 1. Provision a VM

- **Minimum:** 2GB RAM, 1 vCPU, 25GB SSD
- **Recommended:** 4GB RAM, 2 vCPU, 50GB SSD
- **OS:** Ubuntu 22.04 LTS

### 2. Install Docker

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
sudo apt install docker-compose-plugin -y
```

### 3. Configure Environment

```bash
git clone https://github.com/dataforaction-tom/llmstxt-social.git
cd llmstxt-social
cp .env.example .env
```

Edit `.env` and set at least:

```env
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_MONITORING_PRICE_ID=price_...
VITE_STRIPE_PUBLIC_KEY=pk_live_...
RESEND_API_KEY=re_...
SECRET_KEY=your-random-64-character-string
POSTGRES_PASSWORD=your-db-password
BASE_URL=https://yourdomain.com
FRONTEND_URL=https://yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

Optional templates/scripts:

- `.env.production.example` for a minimal paid-tier config.
- `deploy/scripts/check-env.sh` to validate required keys before deploy.
- `deploy/scripts/setup-vm.sh yourdomain.com` to install Docker/Caddy, copy the repo to `/opt/llmstxt-social`, and start the systemd unit.
- `deploy/scripts/update-stack.sh` to pull, rebuild, migrate, and restart the stack.

### 4. Run the Stack

```bash
docker compose -f docker-compose.single.yml up -d --build
./deploy/scripts/check-env.sh .env
docker compose -f docker-compose.single.yml exec api alembic upgrade head
```

### 5. Add a Reverse Proxy (Recommended)

Run Caddy on the VM to expose port 80/443 with automatic HTTPS and proxy to `localhost:8000`.
This single domain serves both the API and the web UI.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Copy `deploy/caddy/Caddyfile` to `/etc/caddy/Caddyfile` and set your domain:

```bash
sudo cp deploy/caddy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/yourdomain.com/yourdomain.com/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 6. Verify

```bash
curl https://yourdomain.com/health
open https://yourdomain.com
```

### Optional: Run via systemd

```bash
sudo mkdir -p /opt/llmstxt-social
sudo rsync -a ./ /opt/llmstxt-social/
sudo cp deploy/systemd/llmstxt.service /etc/systemd/system/llmstxt.service
sudo systemctl daemon-reload
sudo systemctl enable llmstxt.service
sudo systemctl start llmstxt.service
```

---

## Railway Deployment

Railway is the easiest option for deploying this monorepo.

**Estimated cost:** $5-40/month depending on usage

### Quick Start

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/dataforaction-tom/llmstxt-social)

> **Note:** Railway requires manual configuration for monorepos with multiple services. The button above will create a project from this repo, but you'll need to follow the steps below to add all services (API, Worker, Web) and databases.

For a true one-click experience, you can [create a Railway Template](https://docs.railway.app/guides/templates) from your configured project and share that template link instead.

### Step 1: Create Railway Project

1. Go to https://railway.app and sign in
2. Click **"New Project"**
3. Select **"Empty Project"**

### Step 2: Add PostgreSQL Database

1. In your project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Wait for it to provision
4. Note: Railway automatically creates the `DATABASE_URL` variable

### Step 3: Add Redis Database

1. Click **"+ New"**
2. Select **"Database"** → **"Redis"**
3. Wait for it to provision
4. Note: Railway automatically creates the `REDIS_URL` variable

### Step 4: Deploy the API Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select your `llmstxt-social` repository
3. Railway will detect it as a Python project - **cancel the auto-deploy**
4. Click on the service, go to **"Settings"**

**Configure Build Settings:**
- **Builder:** Dockerfile
- **Dockerfile Path:** `packages/api/Dockerfile`
- **Watch Paths:** `/packages/api/**`, `/packages/core/**`

**Configure Variables** (click "Variables" tab):
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ANTHROPIC_API_KEY=sk-ant-your-key-here
SECRET_KEY=generate-a-random-64-char-string
ENVIRONMENT=production
CORS_ORIGINS=https://your-web-service.railway.app
```

**Configure Networking:**
- Go to **"Settings"** → **"Networking"**
- Click **"Generate Domain"** to get a public URL
- Note this URL for the web service config

5. Click **"Deploy"**

### Step 5: Run Database Migrations

After API deploys successfully:

1. Go to the API service
2. Click **"Settings"** → **"Deploy"**
3. Under **"Cron Jobs"** or use the Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Run migrations
railway run -s api alembic upgrade head
```

Alternatively, add a release command in Settings → Deploy:
- **Release Command:** `alembic upgrade head`

### Step 6: Deploy the Celery Worker

1. Click **"+ New"** → **"GitHub Repo"**
2. Select the same `llmstxt-social` repository
3. Rename service to `worker` (click service name)
4. Go to **"Settings"**

**Configure Build Settings:**
- **Builder:** Dockerfile
- **Dockerfile Path:** `packages/api/Dockerfile`
- **Watch Paths:** `/packages/api/**`, `/packages/core/**`

**Configure Deploy Settings:**
- **Start Command:** `celery -A llmstxt_api.tasks.celery worker -l info`

**Configure Variables:**
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ANTHROPIC_API_KEY=sk-ant-your-key-here
CHARITY_COMMISSION_API_KEY=your-key-if-available
```

5. Click **"Deploy"**

### Step 7: Deploy the Web Frontend

1. Click **"+ New"** → **"GitHub Repo"**
2. Select the same `llmstxt-social` repository
3. Rename service to `web`
4. Go to **"Settings"**

**Configure Build Settings:**
- **Root Directory:** `packages/web`
- **Builder:** Dockerfile

**Configure Variables:**
```
VITE_API_URL=https://your-api-service.railway.app
VITE_STRIPE_PUBLIC_KEY=pk_live_your-key (optional)
```

**Configure Networking:**
- Go to **"Settings"** → **"Networking"**
- Click **"Generate Domain"**

5. Click **"Deploy"**

### Step 8: Update CORS

Go back to your **API** service and update `CORS_ORIGINS` with your actual web URL:
```
CORS_ORIGINS=https://web-production-xxxx.railway.app
```

### Railway Project Structure

Your Railway project should now look like:

```
llmstxt-social (Project)
├── Postgres (Database)
├── Redis (Database)
├── api (Service) - FastAPI backend
├── worker (Service) - Celery worker
└── web (Service) - React frontend
```

### Verify Deployment

1. Visit your web URL: `https://web-xxx.railway.app`
2. Check API health: `https://api-xxx.railway.app/health`
3. View API docs: `https://api-xxx.railway.app/docs`

---

## DigitalOcean Deployment

DigitalOcean App Platform offers more control and predictable pricing.

**Estimated cost:** $20-50/month

### One-Click Deploy (Recommended)

[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/dataforaction-tom/llmstxt-social/tree/main)

This repository includes a `.do/app.yaml` that automatically configures:
- PostgreSQL database
- Redis database
- API service (FastAPI)
- Worker service (Celery)
- Web frontend (React)

**After clicking the button:**

1. DigitalOcean will detect the app spec and show the pre-configured services
2. Review the configuration and click **"Next"**
3. Add required secrets in the **"Environment Variables"** section:
   - `ANTHROPIC_API_KEY` - Your Claude API key
   - `SECRET_KEY` - Generate with `openssl rand -hex 32`
4. Click **"Create Resources"**
5. Wait for deployment (5-10 minutes)
6. Run database migrations:
   - Go to your app → `api` service → **"Console"** tab
   - Run: `alembic upgrade head`

**Or deploy via CLI:**

```bash
# Install doctl
brew install doctl  # or see https://docs.digitalocean.com/reference/doctl/how-to/install/

# Authenticate
doctl auth init

# Deploy from app spec
doctl apps create --spec .do/app.yaml

# After deployment, run migrations
doctl apps exec <app-id> --component api -- alembic upgrade head
```

---

### Manual Setup (Alternative)

If you prefer to configure services manually or need more control:

#### Step 1: Create Managed Databases

##### Create PostgreSQL Database

1. Go to https://cloud.digitalocean.com/databases
2. Click **"Create Database Cluster"**
3. Choose:
   - **Engine:** PostgreSQL 15
   - **Plan:** Basic ($15/month) or higher
   - **Datacenter:** Choose your region
   - **Name:** `llmstxt-db`
4. Click **"Create Database Cluster"**
5. Wait for provisioning (takes 5-10 minutes)
6. Create a database named `llmstxt`:
   - Go to **"Users & Databases"** tab
   - Add database: `llmstxt`
7. Copy the connection string from **"Connection Details"**

##### Create Redis Database

1. Go to https://cloud.digitalocean.com/databases
2. Click **"Create Database Cluster"**
3. Choose:
   - **Engine:** Redis
   - **Plan:** Basic ($15/month)
   - **Name:** `llmstxt-redis`
4. Copy the connection string

#### Step 2: Create App Platform Application

1. Go to https://cloud.digitalocean.com/apps
2. Click **"Create App"**
3. Select **"GitHub"** and authorize access
4. Select your `llmstxt-social` repository
5. Select branch: `main`

#### Step 3: Configure API Service

1. On the Resources screen, click **"Edit"** on the detected service
2. Configure:
   - **Name:** `api`
   - **Resource Type:** Web Service
   - **Source Directory:** `/` (root)
   - **Dockerfile Path:** `packages/api/Dockerfile`
   - **HTTP Port:** `8000`
   - **Instance Size:** Basic ($5/month) or higher

3. Add environment variables:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:25060/llmstxt?sslmode=require
REDIS_URL=rediss://default:pass@host:25061
ANTHROPIC_API_KEY=sk-ant-your-key
SECRET_KEY=your-random-secret-key
ENVIRONMENT=production
```

#### Step 4: Add Worker Service

1. Click **"+ Add Resource"** → **"Service from Source"**
2. Same repo, same branch
3. Configure:
   - **Name:** `worker`
   - **Resource Type:** Worker
   - **Source Directory:** `/` (root)
   - **Dockerfile Path:** `packages/api/Dockerfile`
   - **Run Command:** `celery -A llmstxt_api.tasks.celery worker -l info`
   - **Instance Size:** Basic ($5/month)

4. Add same environment variables as API (DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY)

#### Step 5: Add Web Frontend Service

1. Click **"+ Add Resource"** → **"Service from Source"**
2. Same repo, same branch
3. Configure:
   - **Name:** `web`
   - **Resource Type:** Web Service
   - **Source Directory:** `packages/web`
   - **Dockerfile Path:** `Dockerfile` (relative to source directory)
   - **HTTP Port:** `80`
   - **Instance Size:** Basic ($5/month)

4. Add environment variables:
```
VITE_API_URL=${api.PUBLIC_URL}
```

#### Step 6: Configure App Settings

1. Click **"Next"** to go to Environment settings
2. Set **App-Level Environment Variables** (shared across services):
```
ENVIRONMENT=production
```

#### Step 7: Configure Routing

1. Go to **"Settings"** → **"Domains"**
2. Add custom domain or use the provided `.ondigitalocean.app` domain
3. Configure routes:
   - `/api/*` → `api` service
   - `/*` → `web` service

Or use separate subdomains:
- `api.yourdomain.com` → `api` service
- `app.yourdomain.com` → `web` service

#### Step 8: Deploy

1. Review all settings
2. Click **"Create Resources"**
3. Wait for build and deployment

#### Step 9: Run Migrations

1. Go to your app in App Platform
2. Click on the `api` service
3. Go to **"Console"** tab
4. Run:
```bash
alembic upgrade head
```

Or use doctl CLI:
```bash
doctl apps create-deployment <app-id> --wait
doctl apps exec <app-id> --component api -- alembic upgrade head
```

#### App Spec (Optional)

You can also define your app using an `app.yaml` spec file:

```yaml
# .do/app.yaml
name: llmstxt-social
region: lon
databases:
  - engine: PG
    name: db
    num_nodes: 1
    size: db-s-dev-database
    version: "15"
  - engine: REDIS
    name: redis
    num_nodes: 1
    size: db-s-dev-database
    version: "7"

services:
  - name: api
    dockerfile_path: packages/api/Dockerfile
    source_dir: /
    http_port: 8000
    instance_count: 1
    instance_size_slug: basic-xxs
    routes:
      - path: /api
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
      - key: REDIS_URL
        scope: RUN_TIME
        value: ${redis.DATABASE_URL}
      - key: ANTHROPIC_API_KEY
        scope: RUN_TIME
        type: SECRET
      - key: SECRET_KEY
        scope: RUN_TIME
        type: SECRET
      - key: ENVIRONMENT
        value: production

  - name: web
    dockerfile_path: Dockerfile
    source_dir: packages/web
    http_port: 80
    instance_count: 1
    instance_size_slug: basic-xxs
    routes:
      - path: /
    envs:
      - key: VITE_API_URL
        value: ${api.PUBLIC_URL}

workers:
  - name: worker
    dockerfile_path: packages/api/Dockerfile
    source_dir: /
    instance_count: 1
    instance_size_slug: basic-xxs
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
      - key: REDIS_URL
        scope: RUN_TIME
        value: ${redis.DATABASE_URL}
      - key: ANTHROPIC_API_KEY
        scope: RUN_TIME
        type: SECRET
```

Deploy with:
```bash
doctl apps create --spec .do/app.yaml
```

---

## Self-Hosted VPS

For deployment on your own server (DigitalOcean Droplet, AWS EC2, Hetzner, etc.)

**Estimated cost:** $10-20/month for a basic VPS

### Step 1: Provision Server

- **Minimum specs:** 2GB RAM, 1 vCPU, 25GB SSD
- **Recommended:** 4GB RAM, 2 vCPU, 50GB SSD
- **OS:** Ubuntu 22.04 LTS

### Step 2: Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Logout and login again for group changes
```

### Step 3: Clone and Configure

```bash
# Clone repository
git clone https://github.com/dataforaction-tom/llmstxt-social.git
cd llmstxt-social

# Create environment file
cp .env.example .env
nano .env
```

Edit `.env` with production values:
```env
# Required
ANTHROPIC_API_KEY=sk-ant-your-key

# Security - generate with: openssl rand -hex 32
SECRET_KEY=your-random-64-character-string

# Production settings
ENVIRONMENT=production
CORS_ORIGINS=https://yourdomain.com

# Optional: Stripe (for payments)
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLIC_KEY=pk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### Step 4: Start Services

```bash
# Build and start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Check status
docker compose ps
```

### Step 5: Configure Reverse Proxy (Nginx)

Install Nginx on the host:

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

Create Nginx config:

```bash
sudo nano /etc/nginx/sites-available/llmstxt
```

```nginx
# API backend
server {
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# Web frontend
server {
    server_name app.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable and get SSL:

```bash
sudo ln -s /etc/nginx/sites-available/llmstxt /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificates
sudo certbot --nginx -d api.yourdomain.com -d app.yourdomain.com
```

### Step 6: Set Up Auto-Updates (Optional)

Create update script:

```bash
nano ~/update-llmstxt.sh
```

```bash
#!/bin/bash
cd ~/llmstxt-social
git pull
docker compose build
docker compose up -d
docker compose exec -T api alembic upgrade head
```

```bash
chmod +x ~/update-llmstxt.sh
```

---

## Environment Variables

### Required (All Environments)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for generation |

### Required (Production)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | Random secret for JWT signing (64+ chars) |
| `ENVIRONMENT` | Set to `production` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) |

### Required (Paid Tier)

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PUBLIC_KEY` | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `CHARITY_COMMISSION_API_KEY` | - | For UK charity enrichment |
| `RESEND_API_KEY` | - | For email notifications |
| `FREE_TIER_DAILY_LIMIT` | 10 | Rate limit for free tier |

---

## Post-Deployment

### Security Checklist

- [ ] `SECRET_KEY` is a random 64+ character string
- [ ] Using Stripe **live** keys (not test) for production
- [ ] HTTPS enabled on all endpoints
- [ ] `CORS_ORIGINS` restricted to your domains
- [ ] Database has secure password
- [ ] Database backups configured
- [ ] Error monitoring set up (Sentry recommended)

### Verify Deployment

```bash
# Check API health
curl https://api.yourdomain.com/health

# Check API docs
open https://api.yourdomain.com/docs

# Test generation
open https://app.yourdomain.com
```

### Set Up Stripe Webhooks (for paid tier)

1. Go to https://dashboard.stripe.com/webhooks
2. Click **"Add endpoint"**
3. Enter URL: `https://api.yourdomain.com/webhooks/stripe`
4. Select events:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
5. Copy the signing secret to `STRIPE_WEBHOOK_SECRET`

### Monitoring

**Railway:**
- Built-in metrics in dashboard
- View logs: Click service → "Deployments" → "View Logs"

**DigitalOcean:**
- Built-in metrics in App Platform
- Set up alerts in "Insights" tab

**Self-hosted:**
```bash
# View logs
docker compose logs -f api
docker compose logs -f worker

# Check resource usage
docker stats
```

---

## Troubleshooting

### API won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# - DATABASE_URL incorrect or database not accessible
# - Missing ANTHROPIC_API_KEY
# - Port 8000 already in use
```

### Celery worker not processing jobs

```bash
# Check worker logs
docker compose logs worker

# Verify Redis connection
docker compose exec worker redis-cli -u $REDIS_URL ping
```

### Database migration fails

```bash
# Check current migration state
docker compose exec api alembic current

# Reset if needed (WARNING: destroys data)
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
```

### CORS errors

1. Verify `CORS_ORIGINS` includes your web domain
2. Include protocol: `https://app.yourdomain.com` not `app.yourdomain.com`
3. Restart API after changing environment variables

### Web can't connect to API

1. Check `VITE_API_URL` is set correctly
2. Verify API is accessible from browser
3. Check for mixed content (HTTPS page calling HTTP API)
