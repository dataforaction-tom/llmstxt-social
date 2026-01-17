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

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Default command (can be overridden for worker/beat)
CMD ["uvicorn", "llmstxt_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
