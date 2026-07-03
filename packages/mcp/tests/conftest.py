"""Pytest bootstrap for the MCP package.

``llmstxt_api.config.Settings`` instantiates at module load and requires
several env vars (DB URL, Anthropic key, etc.). The MCP server imports
models and the session factory from ``llmstxt_api``, so those env vars
must be present before the first import. We set dummy defaults here so
tests never need a real Postgres or live API keys.
"""

import os

_TEST_ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql://postgres:postgres@localhost/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_dummy",
    "RESEND_API_KEY": "test-resend-key",
    "SECRET_KEY": "test-secret-key-not-for-prod",
    "ENVIRONMENT": "test",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)