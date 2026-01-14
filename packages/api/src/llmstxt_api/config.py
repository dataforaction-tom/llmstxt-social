"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # Redis
    redis_url: str

    # API Keys
    anthropic_api_key: str
    charity_commission_api_key: str | None = None

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_monitoring_price_id: str | None = None

    # Resend
    resend_api_key: str
    from_email: str = "llmstxt <notifications@llmstxt.io>"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # App Settings
    base_url: str = "http://localhost:8000"
    environment: str = "development"

    # Rate Limiting (free tier)
    free_tier_daily_limit: int = 10

    # Job Settings
    job_expiry_days: int = 30
    max_crawl_pages: int = 30

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
