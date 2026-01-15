"""Add magic_link_tokens table

Revision ID: a1b2c3d4e5f6
Revises: 9ef76566d8f1
Create Date: 2026-01-15 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9ef76566d8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create magic_link_tokens table
    op.create_table(
        'magic_link_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, default=False, server_default='false'),
    )

    # Create indexes
    op.create_index('ix_magic_link_tokens_token', 'magic_link_tokens', ['token'])
    op.create_index('ix_magic_link_tokens_email', 'magic_link_tokens', ['email'])


def downgrade() -> None:
    op.drop_index('ix_magic_link_tokens_email', table_name='magic_link_tokens')
    op.drop_index('ix_magic_link_tokens_token', table_name='magic_link_tokens')
    op.drop_table('magic_link_tokens')
