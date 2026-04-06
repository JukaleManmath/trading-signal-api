from app.database.base import Base
from sqlalchemy import Column, String, UUID, DateTime, func, Float, ForeignKey, PrimaryKeyConstraint
from uuid import uuid4


class PricePoint(Base):
    __tablename__ = "price_points"

    # Postgres requires the partition column (timestamp) to be part of the PK.
    # The constraint is declared explicitly below via __table_args__.
    id = Column(UUID(as_uuid=True), default=uuid4, nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    provider = Column(String, nullable=False)
    raw_data_id = Column(UUID(as_uuid=True), ForeignKey("raw_market_data.id"))

    __table_args__ = (
        PrimaryKeyConstraint("id", "timestamp"),
        # Tell SQLAlchemy this is a partitioned table so autogenerate
        # does not try to recreate it on every `alembic revision`.
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )