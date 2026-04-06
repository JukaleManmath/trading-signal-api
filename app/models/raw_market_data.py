from app.database.base import Base
from sqlalchemy import Column, String, Text, UUID, DateTime, func
from uuid import uuid4

class RawMarketData(Base):
    __tablename__ = "raw_market_data"

    id = Column(UUID(as_uuid=True), default=uuid4, nullable=False, primary_key=True)
    symbol = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_json = Column(Text, nullable=True)





