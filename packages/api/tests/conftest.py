"""Pytest bootstrap for the API package.

``llmstxt_api.config.Settings`` instantiates at module load and requires
several env vars (DB URL, Anthropic key, Stripe keys, etc.). Tests that only
need to introspect SQLAlchemy models or pure utility code shouldn't need
those, so we provide dummy values here. This conftest runs before any test
module is collected, so the env is set in time for the first import.
"""

import os

# Only set vars that aren't already set — preserves real values during
# integration tests run against a live config.
_TEST_ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql://postgres:test@localhost/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
    "RESEND_API_KEY": "test-resend-key",
    "SECRET_KEY": "test-secret-key-not-for-prod",
    "ENVIRONMENT": "test",
}

for key, value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
