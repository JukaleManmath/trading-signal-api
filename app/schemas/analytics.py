from pydantic import BaseModel


class MACDSchema(BaseModel):
    line: float
    signal: float
    histogram: float


class BollingerSchema(BaseModel):
    upper: float
    middle: float
    lower: float
    bandwidth: float


class IndicatorResponse(BaseModel):
    symbol: str
    provider: str
    rsi: float | None
    macd: MACDSchema | None
    bollinger: BollingerSchema | None
    signal: str                  # BUY / SELL / HOLD
    confidence: float            # 0.0 – 1.0
    reasons: list[str]
    price_count: int             # how many price points were used


class RiskResponse(BaseModel):
    portfolio_id: str
    total_value: float
    var_1day_95: float | None    # dollar loss at 95% confidence
    sharpe_ratio: float | None
    max_drawdown: float | None   # e.g. -0.23 = worst 23% drawdown
    correlation_matrix: dict | None
    symbols_analysed: list[str]
    warning: str | None
