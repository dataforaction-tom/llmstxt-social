"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# === Generation Schemas ===


class GenerateRequest(BaseModel):
    """Request to generate llms.txt."""

    url: HttpUrl = Field(..., description="URL of the website to generate llms.txt for")
    template: str = Field(
        "charity",
        description="Template type: charity, funder, public_sector, or startup",
        pattern="^(charity|funder|public_sector|startup)$",
    )
    sector: str | None = Field(
        None,
        description="Sub-sector within template (e.g., 'housing', 'mental_health'). Defaults to 'general'",
    )
    goal: str | None = Field(
        None,
        description="Primary goal for the organisation (e.g., 'more_donors', 'more_customers')",
    )


class GeneratePaidRequest(GenerateRequest):
    """Request for paid tier generation."""

    payment_intent_id: str = Field(..., description="Stripe payment intent ID")


class JobResponse(BaseModel):
    """Response with job information."""

    job_id: UUID = Field(..., description="Unique job ID", validation_alias="id")
    status: str = Field(..., description="Job status: pending, processing, completed, or failed")
    url: str = Field(..., description="URL being processed")
    template: str = Field(..., description="Template type")
    sector: str | None = Field(None, description="Sub-sector within template")
    goal: str | None = Field(None, description="Primary goal")
    tier: str = Field(..., description="Tier: free, paid, or subscription")
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: datetime | None = Field(None, description="Job completion timestamp")
    expires_at: datetime | None = Field(None, description="Job expiration timestamp")

    # Progress tracking
    progress_stage: str | None = Field(None, description="Current stage: crawling, analyzing, generating")
    progress_detail: str | None = Field(None, description="Details about current progress")
    pages_crawled: int | None = Field(None, description="Number of pages crawled so far")
    total_pages: int | None = Field(None, description="Total pages to crawl")

    # Output (only available when completed)
    llmstxt_content: str | None = Field(None, description="Generated llms.txt content")
    assessment_json: dict | None = Field(None, description="Assessment results (paid tier only)")

    # User feedback
    dismissed_findings: list[int] | None = Field(None, description="Indices of findings marked as not relevant")

    # Error (only available when failed)
    error_message: str | None = Field(None, description="Error message if job failed")

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    """Lightweight job status response."""

    job_id: UUID = Field(validation_alias="id")
    status: str
    progress: str | None = None

    class Config:
        from_attributes = True


# === Payment Schemas ===


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a Stripe payment intent."""

    url: HttpUrl = Field(..., description="URL for the generation job")
    template: str = Field(
        "charity",
        description="Template type",
        pattern="^(charity|funder|public_sector|startup)$",
    )
    sector: str | None = Field(
        None,
        description="Sub-sector within template. Defaults to 'general'",
    )
    goal: str | None = Field(
        None,
        description="Primary goal for the organisation",
    )
    customer_email: str | None = Field(None, description="Customer email for linking to account")


class CreatePaymentIntentResponse(BaseModel):
    """Response with payment intent details."""

    client_secret: str = Field(..., description="Stripe client secret for frontend")
    amount: int = Field(..., description="Amount in pence/cents")
    currency: str = Field(default="gbp", description="Currency code")


class WebhookEvent(BaseModel):
    """Stripe webhook event payload."""

    type: str
    data: dict


# === Assessment Schemas ===


class AssessRequest(BaseModel):
    """Request to assess llms.txt quality."""

    url: HttpUrl | None = Field(None, description="URL to generate and assess")
    content: str | None = Field(None, description="Existing llms.txt content to assess")
    template: str | None = Field(
        None, description="Template type (auto-detected if not specified)"
    )


class DismissFindingsRequest(BaseModel):
    """Request to dismiss findings and recalculate score."""

    dismissed_indices: list[int] = Field(..., description="Indices of findings to dismiss as not relevant")


class RecalculatedScoreResponse(BaseModel):
    """Response with recalculated assessment scores."""

    overall_score: int = Field(..., description="Recalculated overall score (0-100)")
    completeness_score: int = Field(..., description="Completeness score (unchanged)")
    quality_score: int = Field(..., description="Recalculated quality score (0-100)")
    grade: str = Field(..., description="Recalculated letter grade")
    dismissed_count: int = Field(..., description="Number of findings dismissed")
    remaining_findings: list[dict] = Field(..., description="Findings after dismissals")


class AssessResponse(BaseModel):
    """Assessment results."""

    overall_score: int = Field(..., description="Overall quality score (0-100)")
    completeness_score: int = Field(..., description="Completeness score (0-100)")
    quality_score: int = Field(..., description="Quality score (0-100)")
    grade: str = Field(..., description="Letter grade: A, B, C, D, or F")
    findings: list[dict] = Field(..., description="List of assessment findings")
    recommendations: list[str] = Field(..., description="Top recommendations")


# === User Schemas ===


class UserCreate(BaseModel):
    """Create new user."""

    email: str = Field(..., description="User email address")


class UserResponse(BaseModel):
    """User response."""

    id: str
    email: str
    created_at: datetime
    stripe_customer_id: str | None = None

    class Config:
        from_attributes = True


# === Auth Schemas ===


class MagicLinkRequest(BaseModel):
    """Request to send magic link."""

    email: str = Field(..., description="Email address to send magic link to")


class MagicLinkResponse(BaseModel):
    """Response after sending magic link."""

    message: str
    email: str


class VerifyTokenRequest(BaseModel):
    """Request to verify magic link token."""

    token: str = Field(..., description="Magic link token from email")


class AuthResponse(BaseModel):
    """Response after successful authentication."""

    user: UserResponse
    message: str


# === Subscription Schemas (Phase 2) ===


class SubscriptionCreate(BaseModel):
    """Create monitoring subscription."""

    url: HttpUrl = Field(..., description="URL to monitor")
    template: str = Field(
        "charity",
        description="Template type",
        pattern="^(charity|funder|public_sector|startup)$",
    )
    sector: str | None = Field(
        None,
        description="Sub-sector within template. Defaults to 'general'",
    )
    goal: str | None = Field(
        None,
        description="Primary goal for the organisation",
    )
    email: str | None = Field(None, description="Customer email for checkout")
    success_url: str = Field(..., description="Redirect URL on successful payment")
    cancel_url: str = Field(..., description="Redirect URL on cancelled payment")


class SubscriptionResponse(BaseModel):
    """Subscription details."""

    id: UUID
    url: str
    template: str
    sector: str | None = None
    goal: str | None = None
    frequency: str
    active: bool
    last_check: datetime | None
    last_change_detected: datetime | None
    created_at: datetime
    cancelled_at: datetime | None = None

    class Config:
        from_attributes = True


class CheckoutSessionResponse(BaseModel):
    """Checkout session for subscription."""

    session_id: str = Field(..., description="Stripe checkout session ID")
    checkout_url: str = Field(..., description="URL to redirect user to")


class MonitoringHistoryResponse(BaseModel):
    """Monitoring history entry."""

    id: UUID
    subscription_id: UUID
    checked_at: datetime
    changed: bool
    llmstxt_content: str | None = None
    assessment_json: dict | None = None
    notification_sent: bool
    dismissed_findings: list[int] | None = None

    class Config:
        from_attributes = True


# === Health Check ===


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="API status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment: development, staging, production")


# === Template Options Schemas ===


class SectorOptionSchema(BaseModel):
    """A sector option for a template."""

    id: str = Field(..., description="Sector ID")
    label: str = Field(..., description="Display label")
    description: str = Field(..., description="Description of the sector")


class GoalOptionSchema(BaseModel):
    """A goal option for a template."""

    id: str = Field(..., description="Goal ID")
    label: str = Field(..., description="Display label")


class TemplateOptionsResponse(BaseModel):
    """Available sectors and goals for a template type."""

    template: str = Field(..., description="Template type")
    sectors: list[SectorOptionSchema] = Field(..., description="Available sectors")
    goals: list[GoalOptionSchema] = Field(..., description="Available goals")
    default_sector: str = Field(..., description="Default sector ID")
    default_goal: str = Field(..., description="Default goal ID")
