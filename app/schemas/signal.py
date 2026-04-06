from datetime import datetime

from pydantic import BaseModel


class SignalResponse(BaseModel):
    """Full response for GET /signals/{symbol} — includes indicator snapshot."""
    symbol: str
    provider: str
    signal: str                   # BUY / SELL / HOLD
    confidence: float             # 0.0 – 1.0
    weighted_score: float         # raw score before thresholding
    strategy_mode: str
    price: float                  # price at signal time
    rsi: float | None
    macd_histogram: float | None
    adx: float | None
    timestamp: datetime


class SignalHistoryItem(BaseModel):
    """Single row returned in GET /signals/{symbol}/history."""
    id: str
    signal: str
    confidence: float
    weighted_score: float
    strategy_mode: str
    price: float
    rsi: float | None
    macd_histogram: float | None
    adx: float | None
    timestamp: datetime
