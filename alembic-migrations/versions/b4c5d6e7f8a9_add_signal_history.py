"""add signal_history table

Revision ID: b4c5d6e7f8a9
Revises: f3a1b2c4d5e6
Create Date: 2026-04-06

Stores every computed signal with a snapshot of the key indicators that
drove it (RSI, MACD histogram, ADX). Used by GET /signals/{symbol}/history.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b4c5d6e7f8a9"
down_revision = "f3a1b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_history",
        sa.Column("id", UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("signal", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("weighted_score", sa.Float(), nullable=False),
        sa.Column("strategy_mode", sa.String(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("rsi", sa.Float(), nullable=True),
        sa.Column("macd_histogram", sa.Float(), nullable=True),
        sa.Column("adx", sa.Float(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_signal_history_symbol_ts",
        "signal_history",
        ["symbol", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("idx_signal_history_symbol_ts", table_name="signal_history")
    op.drop_table("signal_history")
