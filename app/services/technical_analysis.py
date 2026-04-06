"""
Technical analysis indicators computed from price_points table.

Note: We only have close prices (no OHLCV data). All indicators use close price only.
"""
import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_points import PricePoint

logger = logging.getLogger(__name__)


@dataclass
class MACDResult:
    line: float
    signal: float
    histogram: float


@dataclass
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float  # (upper - lower) / middle — measures how wide the bands are


@dataclass
class IndicatorResult:
    symbol: str
    rsi: float | None
    macd: MACDResult | None
    bollinger: BollingerResult | None
    price_count: int  # how many price points were used


class TechnicalAnalysisService:
    # Minimum prices needed for each indicator
    RSI_PERIOD = 14
    MACD_SLOW = 26
    MACD_FAST = 12
    MACD_SIGNAL = 9
    BOLLINGER_PERIOD = 20

    # We need at least enough for the slowest indicator
    MIN_PRICES = MACD_SLOW + MACD_SIGNAL  # 35 points to compute MACD with signal line

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute(self, symbol: str, provider: str) -> IndicatorResult:
        prices = await self._fetch_prices(symbol, provider)

        if len(prices) < 2:
            logger.warning("insufficient_prices", extra={"symbol": symbol, "count": len(prices)})
            return IndicatorResult(symbol=symbol, rsi=None, macd=None, bollinger=None, price_count=len(prices))

        arr = np.array(prices, dtype=float)

        rsi = self._compute_rsi(arr) if len(arr) >= self.RSI_PERIOD + 1 else None
        macd = self._compute_macd(arr) if len(arr) >= self.MIN_PRICES else None
        bollinger = self._compute_bollinger(arr) if len(arr) >= self.BOLLINGER_PERIOD else None

        return IndicatorResult(
            symbol=symbol,
            rsi=rsi,
            macd=macd,
            bollinger=bollinger,
            price_count=len(arr),
        )

    async def _fetch_prices(self, symbol: str, provider: str) -> list[float]:
        """Fetch the most recent 100 prices ordered oldest → newest (numpy needs chronological order)."""
        result = await self._db.execute(
            select(PricePoint.price)
            .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
            .order_by(desc(PricePoint.timestamp))
            .limit(100)
        )
        rows = result.scalars().all()
        # rows are newest-first; reverse so index 0 = oldest
        return list(reversed(rows))

    def _compute_rsi(self, prices: np.ndarray) -> float:
        """
        RSI (Relative Strength Index) over the last RSI_PERIOD prices.

        Steps:
        1. Compute daily price changes (deltas).
        2. Separate into gains (positive deltas) and losses (absolute negative deltas).
        3. Average gain / average loss = RS.
        4. RSI = 100 - (100 / (1 + RS)).
        """
        deltas = np.diff(prices[-(self.RSI_PERIOD + 1):])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if avg_loss == 0:
            return 100.0  # no losses at all → maximum strength

        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """
        Exponential Moving Average.

        EMA gives more weight to recent prices than a simple average.
        The multiplier k = 2 / (period + 1) controls how fast it reacts.
        """
        k = 2.0 / (period + 1)
        ema = np.empty(len(prices))
        ema[0] = prices[0]  # seed with first price
        for i in range(1, len(prices)):
            ema[i] = prices[i] * k + ema[i - 1] * (1 - k)
        return ema

    def _compute_macd(self, prices: np.ndarray) -> MACDResult:
        """
        MACD (Moving Average Convergence Divergence).

        MACD line    = EMA(12) - EMA(26)
        Signal line  = EMA(9) of the MACD line
        Histogram    = MACD line - Signal line

        A positive histogram means MACD is above its signal → bullish.
        A negative histogram means MACD is below its signal → bearish.
        """
        ema_fast = self._ema(prices, self.MACD_FAST)
        ema_slow = self._ema(prices, self.MACD_SLOW)
        macd_line = ema_fast - ema_slow

        signal_line = self._ema(macd_line, self.MACD_SIGNAL)

        return MACDResult(
            line=round(float(macd_line[-1]), 4),
            signal=round(float(signal_line[-1]), 4),
            histogram=round(float(macd_line[-1] - signal_line[-1]), 4),
        )

    def _compute_bollinger(self, prices: np.ndarray) -> BollingerResult:
        """
        Bollinger Bands over last BOLLINGER_PERIOD prices.

        Middle band = simple moving average (SMA).
        Upper band  = SMA + 2 * standard deviation.
        Lower band  = SMA - 2 * standard deviation.

        Bandwidth = (upper - lower) / middle — tells you how volatile the stock is right now.
        """
        window = prices[-self.BOLLINGER_PERIOD:]
        middle = float(window.mean())
        std = float(window.std(ddof=1))  # ddof=1 = sample standard deviation

        upper = middle + 2 * std
        lower = middle - 2 * std
        bandwidth = (upper - lower) / middle if middle != 0 else 0.0

        return BollingerResult(
            upper=round(upper, 4),
            middle=round(middle, 4),
            lower=round(lower, 4),
            bandwidth=round(bandwidth, 4),
        )
