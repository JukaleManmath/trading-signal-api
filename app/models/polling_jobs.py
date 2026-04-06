from app.database.base import Base
from sqlalchemy import Column, String,UUID, DateTime, func, Integer
from uuid import uuid4
from enum import Enum
from sqlalchemy import Enum as SqlEnum

class SuccessCriteria(str, Enum):
    success = "success"
    failed = "failed"
    pending = "pending"

class PollingJob(Base):
    __tablename__= "polling_jobs"

    id = Column(UUID(as_uuid=True), default=uuid4, nullable=False, primary_key=True)
    symbol = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    interval = Column(Integer, nullable=False)
    status = Column(SqlEnum(SuccessCriteria) , nullable=False, server_default="pending")
    last_polled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)