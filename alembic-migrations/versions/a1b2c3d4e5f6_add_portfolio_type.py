"""Add portfolio_type column to portfolios

Revision ID: a1b2c3d4e5f6
Revises: e5f6a7b8c9d0
Create Date: 2026-03-30 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE portfolios
        ADD COLUMN IF NOT EXISTS portfolio_type VARCHAR(10) NOT NULL DEFAULT 'stock'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE portfolios DROP COLUMN IF EXISTS portfolio_type")
