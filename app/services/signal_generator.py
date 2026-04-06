"""
Composite signal generator.

Takes indicator values from TechnicalAnalysisService and applies rule-based voting
to produce a single BUY / SELL / HOLD decision with a confidence score.

Voting rules:
  RSI < 30          → +1 BUY   (oversold — stock beaten down, likely to bounce)
  RSI > 70          → +1 SELL  (overbought — stock stretched too high, likely to pull back)
  MACD histogram > 0 → +1 BUY  (MACD line above signal line → bullish momentum)
  MACD histogram < 0 → +1 SELL (MACD line below signal line → bearish momentum)
  Price <= lower band → +1 BUY  (price at a historical low relative to recent range)
  Price >= upper band → +1 SELL (price at a historical high relative to recent range)

Confidence = votes_for_winning_side / total_possible_votes (3 indicators, so max 3 votes).
"""
import logging
from dataclasses import dataclass, field
from enum import Enum

from app.services.technical_analysis import IndicatorResult

logger = logging.getLogger(__name__)


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SignalResult:
    signal: Signal
    confidence: float        # 0.0 – 1.0
    reasons: list[str] = field(default_factory=list)
    buy_votes: int = 0
    sell_votes: int = 0
    total_votes: int = 0     # how many indicators had enough data to vote


class SignalGenerator:
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    def generate(self, indicators: IndicatorResult, current_price: float) -> SignalResult:
        buy_votes = 0
        sell_votes = 0
        total_votes = 0
        reasons: list[str] = []

        # --- RSI vote ---
        if indicators.rsi is not None:
            total_votes += 1
            if indicators.rsi < self.RSI_OVERSOLD:
                buy_votes += 1
                reasons.append(f"RSI {indicators.rsi} is oversold (< {self.RSI_OVERSOLD})")
            elif indicators.rsi > self.RSI_OVERBOUGHT:
                sell_votes += 1
                reasons.append(f"RSI {indicators.rsi} is overbought (> {self.RSI_OVERBOUGHT})")

        # --- MACD vote ---
        if indicators.macd is not None:
            total_votes += 1
            if indicators.macd.histogram > 0:
                buy_votes += 1
                reasons.append(f"MACD histogram {indicators.macd.histogram} is positive (bullish momentum)")
            elif indicators.macd.histogram < 0:
                sell_votes += 1
                reasons.append(f"MACD histogram {indicators.macd.histogram} is negative (bearish momentum)")

        # --- Bollinger Bands vote ---
        if indicators.bollinger is not None:
            total_votes += 1
            if current_price <= indicators.bollinger.lower:
                buy_votes += 1
                reasons.append(
                    f"Price {current_price} at or below lower Bollinger band {indicators.bollinger.lower}"
                )
            elif current_price >= indicators.bollinger.upper:
                sell_votes += 1
                reasons.append(
                    f"Price {current_price} at or above upper Bollinger band {indicators.bollinger.upper}"
                )

        # --- Tally ---
        if total_votes == 0:
            logger.warning("no_indicator_data_for_signal", extra={"symbol": indicators.symbol})
            return SignalResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reasons=["Insufficient price history to compute any indicator"],
                buy_votes=0,
                sell_votes=0,
                total_votes=0,
            )

        if buy_votes > sell_votes:
            signal = Signal.BUY
            confidence = round(buy_votes / total_votes, 2)
        elif sell_votes > buy_votes:
            signal = Signal.SELL
            confidence = round(sell_votes / total_votes, 2)
        else:
            # Tie or no votes on either side → HOLD
            signal = Signal.HOLD
            confidence = 0.0
            if not reasons:
                reasons.append("No indicator triggered a directional signal")

        return SignalResult(
            signal=signal,
            confidence=confidence,
            reasons=reasons,
            buy_votes=buy_votes,
            sell_votes=sell_votes,
            total_votes=total_votes,
        )
