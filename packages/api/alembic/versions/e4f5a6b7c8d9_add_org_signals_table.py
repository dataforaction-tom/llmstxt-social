"""Add org_signals table for funder signalling.

Implements the essay vision: 'Funders can signal interest, changing funding
temporality from artificial deadlines to responsive ecosystem dynamics.'
Phase 1 only has ``signal_type='interest'``; the column is a string enum so
expansion doesn't need a migration.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "idea_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("org_ideas.id"),
            nullable=True,
        ),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("signal_type", sa.String(20), nullable=False, server_default="interest"),
        sa.Column("funder_name", sa.String(200), nullable=True),
        sa.Column("funder_email", sa.String(320), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_org_signals_org_id", "org_signals", ["org_id"])
    op.create_index("ix_org_signals_idea_id", "org_signals", ["idea_id"])


def downgrade() -> None:
    op.drop_index("ix_org_signals_idea_id", table_name="org_signals")
    op.drop_index("ix_org_signals_org_id", table_name="org_signals")
    op.drop_table("org_signals")