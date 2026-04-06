"""
Composite signal generator — weighted scoring with strategy modes.

Each indicator contributes a directional score (+1.0 BUY, -1.0 SELL, 0.0 neutral)
multiplied by its weight for the active strategy. Weights are read from settings
so they can be tuned via .env without code changes.

Strategy modes
--------------
trend-following  MACD + EMA + OBV carry more weight — these measure momentum.
mean-reversion   RSI + Bollinger carry more weight — these measure stretch from baseline.
caution          Balanced weights + a higher score threshold before firing a signal.

ADX as a regime modifier (not a directional voter)
---------------------------------------------------
ADX measures trend *strength* (0–100), not direction.
  > 25  → strong trend
  < 20  → weak trend / ranging market

In trend-following mode:  ADX > 25 amplifies the score (×1.2); ADX < 20 dampens (×0.8).
In mean-reversion mode:   ADX < 20 amplifies (×1.2 — ranging = good for reversion);
                          ADX > 25 dampens (×0.8 — trending = bad for reversion).
In caution mode:          ADX is ignored as a modifier.

Real-life analogy
-----------------
Professional quant funds do not hand-pick these weights. They compute the Information
Coefficient (IC) of each indicator — a correlation between the indicator's signal and
actual next-period returns — over years of backtested history. Weights are then set
proportional to IC, and the whole system is optimised for Sharpe ratio. Our weights
are reasonable defaults that can be overridden via .env once historical data exists
for backtesting.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings
from app.services.technical_analysis import IndicatorResult

logger = logging.getLogger(__name__)

# HOLD threshold: minimum |score| required to fire a directional signal.
# Caution mode uses a higher threshold — more evidence required.
_HOLD_THRESHOLD_DEFAULT = 0.15
_HOLD_THRESHOLD_CAUTION = 0.30

# ADX multipliers applied to the final score in trend-following / mean-reversion modes.
_ADX_STRONG_TREND = 25.0
_ADX_WEAK_TREND = 20.0
_ADX_AMPLIFY = 1.2
_ADX_DAMPEN = 0.8


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyMode(str, Enum):
    TREND_FOLLOWING = "trend-following"
    MEAN_REVERSION = "mean-reversion"
    CAUTION = "caution"


@dataclass
class SignalResult:
    signal: Signal
    confidence: float           # 0.0 – 1.0
    strategy_mode: str
    weighted_score: float       # raw score before thresholding — useful for debugging / logging
    reasons: list[str] = field(default_factory=list)


class SignalGenerator:
    """
    Generates a BUY / SELL / HOLD signal from a set of computed indicators.

    Weights are loaded from settings at construction time so the generator
    always reflects the current configuration without requiring a restart
    beyond the initial app boot.
    """

    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    def __init__(self) -> None:
        # Build weight maps from settings — one dict per strategy.
        # Keys match the scoring methods below.
        self._weights: dict[StrategyMode, dict[str, float]] = {
            StrategyMode.TREND_FOLLOWING: {
                "macd":      settings.tf_weight_macd,
                "ema":       settings.tf_weight_ema,
                "obv":       settings.tf_weight_obv,
                "rsi":       settings.tf_weight_rsi,
                "bollinger": settings.tf_weight_bollinger,
            },
            StrategyMode.MEAN_REVERSION: {
                "rsi":       settings.mr_weight_rsi,
                "bollinger": settings.mr_weight_bollinger,
                "macd":      settings.mr_weight_macd,
                "ema":       settings.mr_weight_ema,
                "obv":       settings.mr_weight_obv,
            },
            StrategyMode.CAUTION: {
                "bollinger": settings.ca_weight_bollinger,
                "rsi":       settings.ca_weight_rsi,
                "macd":      settings.ca_weight_macd,
                "ema":       settings.ca_weight_ema,
                "obv":       settings.ca_weight_obv,
            },
        }

    def generate(
        self,
        indicators: IndicatorResult,
        current_price: float,
        strategy_mode: StrategyMode = StrategyMode.TREND_FOLLOWING,
    ) -> SignalResult:
        weights = self._weights[strategy_mode]
        reasons: list[str] = []
        score = 0.0
        max_possible = 0.0

        # --- RSI ---
        if indicators.rsi is not None:
            w = weights["rsi"]
            max_possible += w
            if indicators.rsi < self.RSI_OVERSOLD:
                score += w
                reasons.append(f"RSI {indicators.rsi} oversold (< {self.RSI_OVERSOLD}) [w={w}]")
            elif indicators.rsi > self.RSI_OVERBOUGHT:
                score -= w
                reasons.append(f"RSI {indicators.rsi} overbought (> {self.RSI_OVERBOUGHT}) [w={w}]")

        # --- MACD ---
        if indicators.macd is not None:
            w = weights["macd"]
            max_possible += w
            if indicators.macd.histogram > 0:
                score += w
                reasons.append(f"MACD histogram {indicators.macd.histogram} positive — bullish momentum [w={w}]")
            elif indicators.macd.histogram < 0:
                score -= w
                reasons.append(f"MACD histogram {indicators.macd.histogram} negative — bearish momentum [w={w}]")

        # --- Bollinger Bands ---
        if indicators.bollinger is not None:
            w = weights["bollinger"]
            max_possible += w
            if current_price <= indicators.bollinger.lower:
                score += w
                reasons.append(f"Price {current_price} at/below lower band {indicators.bollinger.lower} [w={w}]")
            elif current_price >= indicators.bollinger.upper:
                score -= w
                reasons.append(f"Price {current_price} at/above upper band {indicators.bollinger.upper} [w={w}]")

        # --- EMA (price position relative to EMA) ---
        if indicators.ema is not None:
            w = weights["ema"]
            max_possible += w
            if current_price > indicators.ema:
                score += w
                reasons.append(f"Price {current_price} above EMA {indicators.ema} — uptrend [w={w}]")
            elif current_price < indicators.ema:
                score -= w
                reasons.append(f"Price {current_price} below EMA {indicators.ema} — downtrend [w={w}]")

        # --- OBV (sign indicates net volume direction) ---
        if indicators.obv is not None:
            w = weights["obv"]
            max_possible += w
            if indicators.obv > 0:
                score += w
                reasons.append(f"OBV {indicators.obv} positive — volume supports upward move [w={w}]")
            elif indicators.obv < 0:
                score -= w
                reasons.append(f"OBV {indicators.obv} negative — volume supports downward move [w={w}]")

        if max_possible == 0.0:
            logger.warning("no_indicator_data_for_signal", extra={"symbol": indicators.symbol})
            return SignalResult(
                signal=Signal.HOLD,
                confidence=0.0,
                strategy_mode=strategy_mode.value,
                weighted_score=0.0,
                reasons=["Insufficient price history to compute any indicator"],
            )

        # --- ADX modifier (regime amplifier / dampener) ---
        if indicators.adx is not None and strategy_mode != StrategyMode.CAUTION:
            if strategy_mode == StrategyMode.TREND_FOLLOWING:
                if indicators.adx > _ADX_STRONG_TREND:
                    score *= _ADX_AMPLIFY
                    reasons.append(f"ADX {indicators.adx} > {_ADX_STRONG_TREND} — strong trend, signal amplified")
                elif indicators.adx < _ADX_WEAK_TREND:
                    score *= _ADX_DAMPEN
                    reasons.append(f"ADX {indicators.adx} < {_ADX_WEAK_TREND} — weak trend, signal dampened")
            elif strategy_mode == StrategyMode.MEAN_REVERSION:
                if indicators.adx < _ADX_WEAK_TREND:
                    score *= _ADX_AMPLIFY
                    reasons.append(f"ADX {indicators.adx} < {_ADX_WEAK_TREND} — ranging market, reversion signal amplified")
                elif indicators.adx > _ADX_STRONG_TREND:
                    score *= _ADX_DAMPEN
                    reasons.append(f"ADX {indicators.adx} > {_ADX_STRONG_TREND} — trending market, reversion signal dampened")

        # --- Tally ---
        hold_threshold = (
            _HOLD_THRESHOLD_CAUTION
            if strategy_mode == StrategyMode.CAUTION
            else _HOLD_THRESHOLD_DEFAULT
        )

        # Clamp score to [-max_possible, max_possible] after ADX modification.
        clamped = max(-max_possible, min(max_possible, score))
        confidence = round(abs(clamped) / max_possible, 2)

        if score > hold_threshold:
            signal = Signal.BUY
        elif score < -hold_threshold:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD
            confidence = 0.0
            if not any("oversold" in r or "overbought" in r or "positive" in r or "negative" in r for r in reasons):
                reasons.append("No indicator triggered a strong enough directional signal")

        logger.info(
            "signal_generated",
            extra={
                "symbol": indicators.symbol,
                "signal": signal.value,
                "score": round(score, 4),
                "confidence": confidence,
                "strategy": strategy_mode.value,
            },
        )

        return SignalResult(
            signal=signal,
            confidence=confidence,
            strategy_mode=strategy_mode.value,
            weighted_score=round(score, 4),
            reasons=reasons,
        )
