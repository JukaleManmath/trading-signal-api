from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, Float, String, Boolean
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class AlertSeverity(str):
    low = "low"
    medium = "medium"
    high = "high"


class AnomalyType(str):
    zscore_spike = "zscore_spike"
    zscore_drop = "zscore_drop"
    ma_crossover = "ma_crossover"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    symbol = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    anomaly_type = Column(
        SqlEnum("zscore_spike", "zscore_drop", "ma_crossover", name="anomalytype", create_type=False),
        nullable=False,
    )
    severity = Column(
        SqlEnum("low", "medium", "high", name="alertseverity", create_type=False),
        nullable=False,
    )
    price = Column(Float, nullable=False)
    z_score = Column(Float, nullable=True)
    fast_ma = Column(Float, nullable=True)
    slow_ma = Column(Float, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
