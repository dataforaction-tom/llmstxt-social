"""Open Org: fine-grained generation status columns on org_profiles.

Adds five nullable columns powering the live-progress display on the Generate
page. The existing ``generation_status`` (pending/generating/ready/failed)
stays as the headline state; the new columns carry the human-readable stage
message, a small payload, and start/finish timestamps.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-19 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "org_profiles",
        sa.Column("generation_stage", sa.String(40), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_message", sa.String(200), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_payload", JSONB(), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_finished_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("org_profiles", "generation_finished_at")
    op.drop_column("org_profiles", "generation_started_at")
    op.drop_column("org_profiles", "generation_payload")
    op.drop_column("org_profiles", "generation_message")
    op.drop_column("org_profiles", "generation_stage")
