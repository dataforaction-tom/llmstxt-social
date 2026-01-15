"""SQLAlchemy database models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from llmstxt_api.database import Base


class User(Base):
    """User model (optional for MVP)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class GenerationJob(Base):
    """Generation job model."""

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # 'free', 'paid', 'subscription'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'pending', 'processing', 'completed', 'failed'

    # Progress tracking
    progress_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pages_crawled: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Output
    llmstxt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Billing
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_paid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_generation_jobs_user_created", "user_id", "created_at"),
        Index("ix_generation_jobs_url_expires", "url", "expires_at"),
        Index("ix_generation_jobs_status", "status"),
    )


class Subscription(Base):
    """Monitoring subscription model (Phase 2)."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # 'weekly', 'monthly'

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_change_detected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Stripe
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MonitoringHistory(Base):
    """Monitoring history model (Phase 2)."""

    __tablename__ = "monitoring_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    llmstxt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class MagicLinkToken(Base):
    """Magic link token for passwordless authentication."""

    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_magic_link_tokens_token", "token"),
        Index("ix_magic_link_tokens_email", "email"),
    )
