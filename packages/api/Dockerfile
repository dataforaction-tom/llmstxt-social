# Dockerfile for llmstxt API (serves web UI in single-VM deploys)

FROM node:18-alpine AS web-build

WORKDIR /web

COPY packages/web/package.json packages/web/package-lock.json* ./
RUN npm ci

COPY packages/web ./
ARG VITE_API_URL=
ARG VITE_STRIPE_PUBLIC_KEY=
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_STRIPE_PUBLIC_KEY=${VITE_STRIPE_PUBLIC_KEY}
RUN npm run build

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy core package
COPY packages/core /app/core

# Install core package
RUN pip install --no-cache-dir -e /app/core

# Copy API package
COPY packages/api /app/api

# Install API package and dependencies
WORKDIR /app/api
RUN pip install --no-cache-dir -e .

# Copy built web assets
COPY --from=web-build /web/dist /app/web/dist

# Install Playwright Chromium for the Celery worker's website-crawl
# fallback (v0.2.6). The api process doesn't use it but shares the image.
# Installing to a world-readable path so the non-root appuser can launch it.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install-deps chromium && \
    playwright install chromium && \
    chmod -R a+rX /ms-playwright

# Create non-root user and celery beat schedule directory
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /var/run/celery && \
    chown appuser:appuser /var/run/celery
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Default command (can be overridden for worker/beat). ``--forwarded-allow-ips``
# is required so uvicorn honors X-Forwarded-For from the reverse proxy — without
# it, RateLimitMiddleware keys on the proxy's IP and the per-IP cap collapses
# to a server-wide cap. See SECURITY-REVIEW.md H1.
CMD ["uvicorn", "llmstxt_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips=127.0.0.1"]
