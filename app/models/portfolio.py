from uuid import uuid4

from sqlalchemy import Column, DateTime, String, UUID, func

from app.database.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    name = Column(String, nullable=False)
    portfolio_type = Column(String(10), nullable=False, server_default="stock")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
