"""Application configuration using Pydantic settings."""

import json

from pydantic_settings import BaseSettings, SettingsConfigDict

from llmstxt_core.llm_providers import build_llm_client


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # Redis
    redis_url: str

    # API Keys
    anthropic_api_key: str
    charity_commission_api_key: str | None = None

    # LLM provider selection. Open Org generation + the strategy/idea creator
    # run through a provider-neutral client (llmstxt_core.llm_providers), so the
    # model and backend are swappable without code changes.
    #   - ``anthropic``  → native SDK (prompt caching + tool use), uses ANTHROPIC_API_KEY
    #   - ``openrouter`` → OpenAI-compatible, uses OPENROUTER_API_KEY
    #   - ``ollama``     → Ollama Cloud (OpenAI-compatible), uses OLLAMA_API_KEY
    # ``llm_model`` overrides the provider's default model (use the provider's
    # own model id, e.g. ``anthropic/claude-3.5-sonnet`` on OpenRouter).
    llm_provider: str = "anthropic"
    llm_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_api_key: str | None = None
    ollama_base_url: str = "https://ollama.com/v1"

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_monitoring_price_id: str | None = None

    # One-time payments kill switch. When False (the default) the free
    # endpoint runs the full pipeline (enrichment + assessment) and the
    # one-time payment endpoints return 403. Monitoring subscriptions are
    # NOT affected — they stay paid via Stripe regardless of this flag.
    payments_enabled: bool = False

    # Resend
    resend_api_key: str
    from_email: str = "llmstxt <onboarding@resend.dev>"
    # From-address for Open Org magic-link emails (must be a Resend-verified
    # domain). Used when the login originates from the Open Org host.
    openorg_from_email: str = "Open Org <hello@openorg.good-ship.co.uk>"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Auth cookie domain — set to ``.good-ship.co.uk`` in production so a
    # single login spans ``llmstxt.social`` and ``openorg.good-ship.co.uk``
    # (locked decision #9). Leave unset locally so dev on ``localhost``
    # keeps working without browser shenanigans around Domain= cookies.
    auth_cookie_domain: str | None = None

    # App Settings
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"

    # Comma-separated origins allowed to set the magic-link base URL (one
    # FastAPI process serves multiple hostnames). Anything not listed falls
    # back to frontend_url — never reflect an unvalidated Origin into a login
    # link (host-header injection / token phishing).
    magic_link_origin_allowlist: str = (
        "https://llmstxt.social,https://openorg.good-ship.co.uk"
    )

    # Rate Limiting (free tier)
    free_tier_daily_limit: int = 10

    # Open Org generate endpoint — per-IP hourly cap. The endpoint is
    # unauthenticated by design (anyone can ask us to generate a profile
    # for a charity number) so this is the only deterrent against abuse.
    # Each generation costs real Anthropic spend.
    open_org_generate_hourly_limit: int = 5

    # /api/auth/magic-link — per-IP hourly cap. The endpoint is
    # unauthenticated and triggers a real email send via Resend, so an
    # attacker could otherwise email-bomb any address. 5/hour is generous
    # for fat-finger retries but stops abuse. See SECURITY-REVIEW.md H2.
    magic_link_hourly_limit: int = 5

    # Job Settings
    job_expiry_days: int = 30
    max_crawl_pages: int = 30

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Web build directory (served by FastAPI in single-VM deploys)
    web_dist_dir: str = "/app/web/dist"

    # Murmurations index — default to the test environment until the
    # ``open_org_profile-v0.1.0`` schema PR is merged upstream. Flip to the
    # production index by overriding these env vars in production.
    murmurations_index_url: str = "https://test-index.murmurations.network/v2"
    murmurations_library_url: str = "https://test-library.murmurations.network/v2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Docker-compose and the frontend set env vars (POSTGRES_PASSWORD,
        # VITE_STRIPE_PUBLIC_KEY, RESEND_FROM_EMAIL) that aren't declared on
        # this model. Pydantic-settings v2 defaults to extra='forbid', which
        # crashes on the real .env file. Ignore them — the vars we care about
        # are declared explicitly above.
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        value = self.cors_origins.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def build_llm_client(self):
        """Construct the configured provider-neutral LLM client.

        Open Org generation + the creator call this instead of instantiating a
        client directly, so switching ``LLM_PROVIDER`` / ``LLM_MODEL`` in the
        environment is all that's needed to change backend.
        """
        return build_llm_client(
            self.llm_provider,
            model=self.llm_model,
            anthropic_api_key=self.anthropic_api_key,
            openrouter_api_key=self.openrouter_api_key,
            openrouter_base_url=self.openrouter_base_url,
            ollama_api_key=self.ollama_api_key,
            ollama_base_url=self.ollama_base_url,
        )


# Global settings instance
settings = Settings()
