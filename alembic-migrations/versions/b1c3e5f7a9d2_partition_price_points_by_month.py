"""Partition price_points by month (RANGE on timestamp)

Revision ID: b1c3e5f7a9d2
Revises: a8565285d7ea
Create Date: 2026-03-18 00:00:00.000000

What this migration does:
  1. Drops the old flat price_points table (no valuable data yet).
  2. Recreates it as a partitioned parent table (PARTITION BY RANGE on timestamp).
     - The primary key becomes (id, timestamp) — Postgres requires the partition
       column to be part of every unique constraint on a partitioned table.
  3. Creates monthly child partitions for 2026-03 through 2027-12.
  4. Creates a catch-all partition for anything beyond 2027-12.
  5. Adds a composite index on (symbol, timestamp DESC) so "latest price for
     symbol X" queries only scan the current month's partition.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c3e5f7a9d2'
down_revision: Union[str, None] = 'a8565285d7ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Monthly partitions we want to pre-create.
# Each tuple is (partition_suffix, range_start, range_end).
# range_start is inclusive, range_end is exclusive — standard Postgres RANGE semantics.
MONTHLY_PARTITIONS = [
    # 2026
    ("2026_03", "2026-03-01", "2026-04-01"),
    ("2026_04", "2026-04-01", "2026-05-01"),
    ("2026_05", "2026-05-01", "2026-06-01"),
    ("2026_06", "2026-06-01", "2026-07-01"),
    ("2026_07", "2026-07-01", "2026-08-01"),
    ("2026_08", "2026-08-01", "2026-09-01"),
    ("2026_09", "2026-09-01", "2026-10-01"),
    ("2026_10", "2026-10-01", "2026-11-01"),
    ("2026_11", "2026-11-01", "2026-12-01"),
    ("2026_12", "2026-12-01", "2027-01-01"),
    # 2027
    ("2027_01", "2027-01-01", "2027-02-01"),
    ("2027_02", "2027-02-01", "2027-03-01"),
    ("2027_03", "2027-03-01", "2027-04-01"),
    ("2027_04", "2027-04-01", "2027-05-01"),
    ("2027_05", "2027-05-01", "2027-06-01"),
    ("2027_06", "2027-06-01", "2027-07-01"),
    ("2027_07", "2027-07-01", "2027-08-01"),
    ("2027_08", "2027-08-01", "2027-09-01"),
    ("2027_09", "2027-09-01", "2027-10-01"),
    ("2027_10", "2027-10-01", "2027-11-01"),
    ("2027_11", "2027-11-01", "2027-12-01"),
    ("2027_12", "2027-12-01", "2028-01-01"),
]


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Drop the old flat table.  The FK from raw_market_data must go    #
    #    first — Postgres won't drop a referenced table.                  #
    # ------------------------------------------------------------------ #
    op.drop_constraint(
        "price_points_raw_data_id_fkey",
        "price_points",
        type_="foreignkey",
    )
    op.drop_table("price_points")

    # ------------------------------------------------------------------ #
    # 2. Create the partitioned parent table.                             #
    #                                                                     #
    #    IMPORTANT: we use execute() with raw SQL here because            #
    #    SQLAlchemy's create_table() helper does not support the          #
    #    PARTITION BY clause — it's a Postgres-specific DDL extension.    #
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE price_points (
            id          UUID        NOT NULL,
            symbol      VARCHAR     NOT NULL,
            price       FLOAT       NOT NULL,
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
            provider    VARCHAR     NOT NULL,
            raw_data_id UUID        REFERENCES raw_market_data(id),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp)
    """)

    # ------------------------------------------------------------------ #
    # 3. Create monthly child partitions.                                 #
    #                                                                     #
    #    Each child table inherits all columns from the parent.           #
    #    Postgres automatically routes INSERT/SELECT to the right child   #
    #    based on the timestamp value.                                    #
    # ------------------------------------------------------------------ #
    for suffix, start, end in MONTHLY_PARTITIONS:
        op.execute(f"""
            CREATE TABLE price_points_{suffix}
            PARTITION OF price_points
            FOR VALUES FROM ('{start}') TO ('{end}')
        """)

    # ------------------------------------------------------------------ #
    # 4. Catch-all partition for rows beyond 2027-12.                     #
    #                                                                     #
    #    Without this, any INSERT with a timestamp after 2027-12-31 would #
    #    raise an error ("no partition found for row").  The catch-all    #
    #    prevents that — it just stores future rows until we add a proper #
    #    partition for that month.                                        #
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE price_points_future
        PARTITION OF price_points
        FOR VALUES FROM ('2028-01-01') TO (MAXVALUE)
    """)

    # ------------------------------------------------------------------ #
    # 5. Composite index on (symbol, timestamp DESC).                     #
    #                                                                     #
    #    When the app queries "give me the latest price for AAPL",        #
    #    Postgres uses this index to jump straight to the most recent     #
    #    row — no full-table scan needed.                                 #
    #                                                                     #
    #    The index is created on the parent; Postgres automatically       #
    #    creates matching indexes on every child partition.               #
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE INDEX idx_price_points_symbol_ts
        ON price_points (symbol, timestamp DESC)
    """)


def downgrade() -> None:
    # Drop the whole partitioned table (cascades to all child partitions).
    op.drop_table("price_points")

    # Recreate the original flat table so previous migrations still work.
    op.create_table(
        "price_points",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("raw_data_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["raw_data_id"], ["raw_market_data.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
