from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Index, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class SignalHistory(Base):
    __tablename__ = "signal_history"

    id = Column(UUID(as_uuid=True), default=uuid4, nullable=False, primary_key=True)
    symbol = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    signal = Column(String, nullable=False)           # BUY / SELL / HOLD
    confidence = Column(Float, nullable=False)
    weighted_score = Column(Float, nullable=False)
    strategy_mode = Column(String, nullable=False)
    price = Column(Float, nullable=False)             # price at signal time — always required
    rsi = Column(Float, nullable=True)                # snapshot of key indicators that drove the signal
    macd_histogram = Column(Float, nullable=True)
    adx = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_signal_history_symbol_ts", "symbol", "timestamp"),
    )
