# Dockerfile for llmstxt API

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

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Default command (can be overridden for worker/beat)
CMD ["uvicorn", "llmstxt_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
