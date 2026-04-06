"""Add alerts table with AlertSeverity and AnomalyType enums

Revision ID: c3f9a12b4e01
Revises: b1c3e5f7a9d2
Create Date: 2026-03-20 00:00:00.000000

What this migration does:
  1. Creates the alertseverity Postgres ENUM type (low/medium/high).
  2. Creates the anomalytype Postgres ENUM type (zscore_spike/zscore_drop/ma_crossover).
  3. Creates the alerts table.
  4. Adds composite index on (symbol, timestamp DESC) for active-alert queries.
  5. Adds index on severity for filtering by urgency.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c3f9a12b4e01'
down_revision: Union[str, None] = 'b1c3e5f7a9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Create Postgres ENUM types explicitly via raw SQL.               #
    #                                                                     #
    #    We use op.execute() rather than letting SQLAlchemy emit CREATE   #
    #    TYPE implicitly so we can reference them with create_type=False  #
    #    in op.create_table() and avoid "type already exists" errors.     #
    # ------------------------------------------------------------------ #
    op.execute("CREATE TYPE alertseverity AS ENUM ('low', 'medium', 'high')")
    op.execute("CREATE TYPE anomalytype AS ENUM ('zscore_spike', 'zscore_drop', 'ma_crossover')")

    # ------------------------------------------------------------------ #
    # 2. Create the alerts table using raw SQL.                           #
    #                                                                     #
    #    We use op.execute() instead of op.create_table() because         #
    #    SQLAlchemy ignores create_type=False on Enum columns and emits   #
    #    an extra CREATE TYPE inside create_table, causing a              #
    #    DuplicateObject error. Raw SQL gives us full control.            #
    #                                                                     #
    #    No FK to price_points — the partitioned PK is (id, timestamp),  #
    #    which would require both columns in the FK. Storing symbol +     #
    #    provider as plain strings is the same pattern used by            #
    #    moving_average.                                                  #
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE alerts (
            id          UUID        NOT NULL DEFAULT gen_random_uuid(),
            symbol      VARCHAR     NOT NULL,
            provider    VARCHAR     NOT NULL,
            anomaly_type anomalytype NOT NULL,
            severity    alertseverity NOT NULL,
            price       FLOAT       NOT NULL,
            z_score     FLOAT,
            fast_ma     FLOAT,
            slow_ma     FLOAT,
            resolved    BOOLEAN     NOT NULL DEFAULT false,
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)

    # ------------------------------------------------------------------ #
    # 3. Indexes.                                                         #
    # ------------------------------------------------------------------ #
    op.execute("CREATE INDEX idx_alerts_symbol_ts ON alerts (symbol, timestamp DESC)")
    op.execute("CREATE INDEX idx_alerts_severity ON alerts (severity)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_alerts_severity")
    op.execute("DROP INDEX IF EXISTS idx_alerts_symbol_ts")
    op.drop_table("alerts")
    op.execute("DROP TYPE anomalytype")
    op.execute("DROP TYPE alertseverity")
