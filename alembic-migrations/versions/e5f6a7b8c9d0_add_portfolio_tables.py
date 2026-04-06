"""Add portfolios and positions tables

Revision ID: e5f6a7b8c9d0
Revises: c3f9a12b4e01
Create Date: 2026-03-20 00:00:00.000000

What this migration does:
  1. Creates the portfolios table.
  2. Creates the positions table with a FK to portfolios.
  3. Adds indexes for common query patterns.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'c3f9a12b4e01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE portfolios (
            id          UUID        NOT NULL DEFAULT gen_random_uuid(),
            name        VARCHAR     NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)

    op.execute("""
        CREATE TABLE positions (
            id              UUID        NOT NULL DEFAULT gen_random_uuid(),
            portfolio_id    UUID        NOT NULL REFERENCES portfolios(id),
            symbol          VARCHAR     NOT NULL,
            provider        VARCHAR     NOT NULL DEFAULT 'finnhub',
            quantity        FLOAT       NOT NULL,
            avg_cost_basis  FLOAT       NOT NULL,
            is_active       BOOLEAN     NOT NULL DEFAULT true,
            opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at       TIMESTAMPTZ,
            PRIMARY KEY (id)
        )
    """)

    op.execute("CREATE INDEX idx_positions_portfolio_id ON positions (portfolio_id)")
    op.execute("CREATE INDEX idx_positions_symbol ON positions (symbol)")
    op.execute("CREATE INDEX idx_positions_active ON positions (portfolio_id, is_active)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_positions_active")
    op.execute("DROP INDEX IF EXISTS idx_positions_symbol")
    op.execute("DROP INDEX IF EXISTS idx_positions_portfolio_id")
    op.drop_table("positions")
    op.drop_table("portfolios")
