"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
    )

    # Create generation_jobs table
    op.create_table(
        'generation_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('template', sa.String(50), nullable=False),
        sa.Column('tier', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('llmstxt_content', sa.Text(), nullable=True),
        sa.Column('assessment_json', JSONB, nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('payment_intent_id', sa.String(255), nullable=True),
        sa.Column('amount_paid', sa.Integer(), nullable=True),
    )

    # Create indexes
    op.create_index('ix_generation_jobs_user_created', 'generation_jobs', ['user_id', 'created_at'])
    op.create_index('ix_generation_jobs_url_expires', 'generation_jobs', ['url', 'expires_at'])
    op.create_index('ix_generation_jobs_status', 'generation_jobs', ['status'])

    # Create subscriptions table (for Phase 2)
    op.create_table(
        'subscriptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('template', sa.String(50), nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('active', sa.Boolean(), default=True),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('last_change_detected', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    )

    # Create monitoring_history table (for Phase 2)
    op.create_table(
        'monitoring_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('subscription_id', UUID(as_uuid=True), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.Column('changed', sa.Boolean(), default=False),
        sa.Column('llmstxt_content', sa.Text(), nullable=True),
        sa.Column('assessment_json', JSONB, nullable=True),
        sa.Column('notification_sent', sa.Boolean(), default=False),
    )


def downgrade() -> None:
    op.drop_table('monitoring_history')
    op.drop_table('subscriptions')
    op.drop_index('ix_generation_jobs_status')
    op.drop_index('ix_generation_jobs_url_expires')
    op.drop_index('ix_generation_jobs_user_created')
    op.drop_table('generation_jobs')
    op.drop_table('users')
