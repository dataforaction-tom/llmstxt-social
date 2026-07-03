"""Settings should ignore extra env vars, not crash on them.

Docker-compose and the frontend set env vars (POSTGRES_PASSWORD,
VITE_STRIPE_PUBLIC_KEY, RESEND_FROM_EMAIL) that aren't declared on the
Settings model. Pydantic v2's default for BaseSettings is extra='ignore',
but we verify that explicitly so a future model_config change can't
silently reintroduce the extra='forbid' regression that blocked all API
test collection.
"""

import os


def test_settings_ignores_extra_env_vars(monkeypatch):
    """Extra env vars present in .env must not crash Settings instantiation."""
    monkeypatch.setenv("POSTGRES_PASSWORD", "dummy-pw")
    monkeypatch.setenv("VITE_STRIPE_PUBLIC_KEY", "pk_test_dummy")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "test@example.com")
    # Should not raise
    from llmstxt_api.config import Settings

    s = Settings()
    assert s.database_url is not None
    assert s.anthropic_api_key is not None