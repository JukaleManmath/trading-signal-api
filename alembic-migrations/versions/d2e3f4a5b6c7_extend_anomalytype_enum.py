"""extend anomalytype enum with risk breach values

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-07

Adds four new values to the anomalytype PostgreSQL enum for risk threshold
breach alerts fired by the risk engine: var_breach, drawdown_breach,
concentration_breach, volatility_breach.

ALTER TYPE ... ADD VALUE cannot run inside a transaction block in PostgreSQL,
so each statement uses op.execute() with COMMIT handled by Alembic's
non-transactional migration context.
"""
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'var_breach'")
    op.execute("ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'drawdown_breach'")
    op.execute("ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'concentration_breach'")
    op.execute("ALTER TYPE anomalytype ADD VALUE IF NOT EXISTS 'volatility_breach'")


def downgrade() -> None:
    # PostgreSQL does not support removing individual enum values.
    # To fully revert, the type must be recreated — which requires
    # rewriting all rows that reference it. Out of scope for this project.
    pass
