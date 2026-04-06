"""
Technical analysis indicators computed from price_points table.

Indicators using close prices only: RSI, MACD, Bollinger Bands, EMA, SMA.
Indicators using OHLCV data: ADX (high/low/close), OBV (close/volume).
ADX and OBV return None when the required columns are not available in the DB.
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
    ema: float | None
    sma: float | None
    adx: float | None
    obv: float | None
    price_count: int  # how many price points were used


class TechnicalAnalysisService:
    RSI_PERIOD = 14
    MACD_SLOW = 26
    MACD_FAST = 12
    MACD_SIGNAL = 9
    BOLLINGER_PERIOD = 20
    EMA_PERIOD = 20
    SMA_PERIOD = 20
    ADX_PERIOD = 14

    MIN_PRICES = MACD_SLOW + MACD_SIGNAL  # 35 — slowest indicator

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute(self, symbol: str, provider: str) -> IndicatorResult:
        rows = await self._fetch_ohlcv(symbol, provider)

        if len(rows) < 2:
            logger.warning("insufficient_prices", extra={"symbol": symbol, "count": len(rows)})
            return IndicatorResult(
                symbol=symbol, rsi=None, macd=None, bollinger=None,
                ema=None, sma=None, adx=None, obv=None, price_count=len(rows),
            )

        closes = np.array([r[0] for r in rows], dtype=float)
        highs = np.array([r[1] for r in rows], dtype=float) if rows[0][1] is not None else None
        lows = np.array([r[2] for r in rows], dtype=float) if rows[0][2] is not None else None
        volumes = np.array([r[3] for r in rows], dtype=float) if rows[0][3] is not None else None

        rsi = self._compute_rsi(closes) if len(closes) >= self.RSI_PERIOD + 1 else None
        macd = self._compute_macd(closes) if len(closes) >= self.MIN_PRICES else None
        bollinger = self._compute_bollinger(closes) if len(closes) >= self.BOLLINGER_PERIOD else None
        ema = round(float(self._ema(closes, self.EMA_PERIOD)[-1]), 4) if len(closes) >= self.EMA_PERIOD else None
        sma = self._compute_sma(closes) if len(closes) >= self.SMA_PERIOD else None
        adx = (
            self._compute_adx(closes, highs, lows)
            if highs is not None and lows is not None and len(closes) >= self.ADX_PERIOD + 1
            else None
        )
        obv = (
            self._compute_obv(closes, volumes)
            if volumes is not None and len(closes) >= 2
            else None
        )

        return IndicatorResult(
            symbol=symbol,
            rsi=rsi,
            macd=macd,
            bollinger=bollinger,
            ema=ema,
            sma=sma,
            adx=adx,
            obv=obv,
            price_count=len(closes),
        )

    async def _fetch_ohlcv(self, symbol: str, provider: str) -> list[tuple]:
        """Fetch the most recent 100 OHLCV rows ordered oldest → newest."""
        result = await self._db.execute(
            select(PricePoint.price, PricePoint.high, PricePoint.low, PricePoint.volume)
            .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
            .order_by(desc(PricePoint.timestamp))
            .limit(100)
        )
        rows = result.all()
        return list(reversed(rows))

    # ------------------------------------------------------------------
    # Indicator computations
    # ------------------------------------------------------------------

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
            return 100.0

        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """
        Exponential Moving Average — returns the full array.

        Used internally by MACD and exposed as a named indicator (last value).
        EMA gives more weight to recent prices via multiplier k = 2 / (period + 1).
        """
        k = 2.0 / (period + 1)
        ema = np.empty(len(prices))
        ema[0] = prices[0]
        for i in range(1, len(prices)):
            ema[i] = prices[i] * k + ema[i - 1] * (1 - k)
        return ema

    def _compute_sma(self, prices: np.ndarray) -> float:
        """Simple Moving Average over last SMA_PERIOD prices."""
        return round(float(prices[-self.SMA_PERIOD:].mean()), 4)

    def _compute_macd(self, prices: np.ndarray) -> MACDResult:
        """
        MACD (Moving Average Convergence Divergence).

        MACD line    = EMA(12) - EMA(26)
        Signal line  = EMA(9) of the MACD line
        Histogram    = MACD line - Signal line

        Positive histogram → bullish momentum. Negative → bearish.
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

        Middle = SMA. Upper = SMA + 2σ. Lower = SMA - 2σ.
        Bandwidth = (upper - lower) / middle — current volatility measure.
        """
        window = prices[-self.BOLLINGER_PERIOD:]
        middle = float(window.mean())
        std = float(window.std(ddof=1))

        upper = middle + 2 * std
        lower = middle - 2 * std
        bandwidth = (upper - lower) / middle if middle != 0 else 0.0

        return BollingerResult(
            upper=round(upper, 4),
            middle=round(middle, 4),
            lower=round(lower, 4),
            bandwidth=round(bandwidth, 4),
        )

    def _compute_adx(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> float:
        """
        ADX (Average Directional Index) — measures trend strength, not direction.

        Steps:
        1. True Range (TR) = max(high-low, |high-prev_close|, |low-prev_close|)
        2. +DM = high - prev_high if it's the larger move upward, else 0
        3. -DM = prev_low - low  if it's the larger move downward, else 0
        4. Smooth TR, +DM, -DM using Wilder's smoothing (RMA)
        5. +DI = 100 * smoothed(+DM) / smoothed(TR)
        6. -DI = 100 * smoothed(-DM) / smoothed(TR)
        7. DX  = 100 * |+DI - -DI| / (+DI + -DI)
        8. ADX = RMA of DX over ADX_PERIOD

        ADX > 25 = strong trend. ADX < 20 = weak/ranging market.
        """
        n = len(closes)
        tr = np.zeros(n)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            high_low = highs[i] - lows[i]
            high_pc = abs(highs[i] - closes[i - 1])
            low_pc = abs(lows[i] - closes[i - 1])
            tr[i] = max(high_low, high_pc, low_pc)

            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]
            plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0.0
            minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0.0

        # Wilder's smoothing (RMA): seed with simple average, then smooth
        period = self.ADX_PERIOD
        atr = np.zeros(n)
        s_plus = np.zeros(n)
        s_minus = np.zeros(n)

        atr[period] = tr[1:period + 1].sum()
        s_plus[period] = plus_dm[1:period + 1].sum()
        s_minus[period] = minus_dm[1:period + 1].sum()

        for i in range(period + 1, n):
            atr[i] = atr[i - 1] - atr[i - 1] / period + tr[i]
            s_plus[i] = s_plus[i - 1] - s_plus[i - 1] / period + plus_dm[i]
            s_minus[i] = s_minus[i - 1] - s_minus[i - 1] / period + minus_dm[i]

        dx_values = []
        for i in range(period, n):
            if atr[i] == 0:
                continue
            plus_di = 100 * s_plus[i] / atr[i]
            minus_di = 100 * s_minus[i] / atr[i]
            di_sum = plus_di + minus_di
            dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum != 0 else 0.0
            dx_values.append(dx)

        if not dx_values:
            return 0.0

        # ADX = simple average of DX values (sufficient for the data window we have)
        return round(float(np.mean(dx_values)), 2)

    def _compute_obv(self, closes: np.ndarray, volumes: np.ndarray) -> float:
        """
        OBV (On-Balance Volume) — cumulative volume momentum indicator.

        Rules:
        - Price up   → add volume to running total
        - Price down → subtract volume from running total
        - Price flat → no change

        Rising OBV with rising price confirms the trend.
        Divergence (price up, OBV down) warns of a weak move.
        """
        obv = 0.0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
        return round(obv, 2)
