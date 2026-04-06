from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, UUID, func

from app.database.base import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String, nullable=False)
    provider = Column(String, nullable=False, default="finnhub")
    quantity = Column(Float, nullable=False)
    avg_cost_basis = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
