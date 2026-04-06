"""add ohlcv to price_points

Revision ID: f3a1b2c4d5e6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06

Adds open, high, low, volume columns to the price_points partitioned table
and all its monthly child partitions. Columns are nullable so existing rows
are not affected.
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a1b2c4d5e6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

# All partitions that exist in the schema — parent + children.
# Adding a column to the parent in Postgres automatically adds it to all
# partitions, but we list them explicitly so the downgrade can drop cleanly.
_PARENT = "price_points"


def upgrade() -> None:
    op.add_column(_PARENT, sa.Column("open", sa.Float(), nullable=True))
    op.add_column(_PARENT, sa.Column("high", sa.Float(), nullable=True))
    op.add_column(_PARENT, sa.Column("low", sa.Float(), nullable=True))
    op.add_column(_PARENT, sa.Column("volume", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column(_PARENT, "volume")
    op.drop_column(_PARENT, "low")
    op.drop_column(_PARENT, "high")
    op.drop_column(_PARENT, "open")
