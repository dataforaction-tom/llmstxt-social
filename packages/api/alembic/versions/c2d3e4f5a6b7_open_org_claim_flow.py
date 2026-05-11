"""Open Org claim flow: org_id on magic-link tokens, generation status on profiles

Adds:
- ``magic_link_tokens.org_id`` (nullable) — populated only for claim tokens.
- ``org_profiles.generation_status`` (default ``pending``) and
  ``org_profiles.generation_error`` (nullable) — track the async generator job.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "magic_link_tokens",
        sa.Column("org_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "org_profiles",
        sa.Column(
            "generation_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "org_profiles",
        sa.Column("generation_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("org_profiles", "generation_error")
    op.drop_column("org_profiles", "generation_status")
    op.drop_column("magic_link_tokens", "org_id")
