from app.database.base import Base
from sqlalchemy import Column, String, Text, UUID, DateTime, func, Float, Integer
from uuid import uuid4

class MovingAverage(Base):
    __tablename__= "moving_average"

    id = Column(UUID(as_uuid=True), default=uuid4, nullable=False, primary_key=True)
    symbol = Column(String, nullable=False)
    average_price = Column(Float, nullable=False)
    interval = Column(Integer, nullable=False)
    provider = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)