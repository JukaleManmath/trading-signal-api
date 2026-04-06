import logging

from sqlalchemy.orm import Session

from app.models.alerts import Alert
from app.models.price_points import PricePoint

logger = logging.getLogger(__name__)

# Z-score detection parameters
Z_SCORE_LOOKBACK = 20
SEVERITY_MEDIUM_THRESHOLD = 3.0
SEVERITY_HIGH_THRESHOLD = 4.0

# MA crossover detection parameters
FAST_MA_WINDOW = 5
SLOW_MA_WINDOW = 20
MA_DIVERGENCE_THRESHOLD = 0.005  # 0.5% — avoids noise during normal drift


class AnomalyDetector:
    """
    Detects price anomalies using two algorithms:
      1. Z-score spike/drop — flags prices > 3σ from the 20-pt rolling mean.
      2. MA crossover — flags when fast MA diverges > 0.5% from slow MA.

    Single responsibility: detection + persistence.
    Completely decoupled from Kafka — the consumer calls this after receiving
    a message; this class doesn't know or care about Kafka.

    DB session is injected at construction time (Dependency Inversion).
    Uses sync Session — called from the blocking Kafka consumer loop.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def detect_and_store(self, symbol: str, provider: str) -> list[Alert]:
        """
        Run both detectors against the most recent prices for this symbol.
        Persists any detected anomalies and returns the newly created Alert rows.
        Returns an empty list if no anomalies are detected or insufficient data.
        """
        prices = self._fetch_recent_prices(symbol, n=max(Z_SCORE_LOOKBACK, SLOW_MA_WINDOW))

        candidates = [
            self._check_zscore(symbol, provider, prices),
            self._check_ma_crossover(symbol, provider, prices),
        ]
        new_alerts = [a for a in candidates if a is not None]

        if new_alerts:
            for alert in new_alerts:
                self.db.add(alert)
            self.db.commit()
            logger.info(f"[AnomalyDetector] {len(new_alerts)} alert(s) stored for {symbol}")

        return new_alerts

    def _fetch_recent_prices(self, symbol: str, n: int) -> list[float]:
        """
        Return up to n most recent prices for symbol, newest first.
        """
        rows = (
            self.db.query(PricePoint)
            .filter_by(symbol=symbol)
            .order_by(PricePoint.timestamp.desc())
            .limit(n)
            .all()
        )
        return [row.price for row in rows]

    def _check_zscore(self, symbol: str, provider: str, prices: list[float]) -> Alert | None:
        """
        Z-score anomaly detection.

        Requires at least Z_SCORE_LOOKBACK (20) prices. Computes rolling mean
        and std; flags the most recent price if |z| >= SEVERITY_MEDIUM_THRESHOLD (3.0).

        Severity:
          medium → 3.0 <= |z| < 4.0
          high   → |z| >= 4.0
        """
        if len(prices) < Z_SCORE_LOOKBACK:
            logger.debug(f"[ZScore] Not enough data for {symbol} (have {len(prices)}, need {Z_SCORE_LOOKBACK})")
            return None

        lookback = prices[:Z_SCORE_LOOKBACK]
        mean = sum(lookback) / Z_SCORE_LOOKBACK
        variance = sum((p - mean) ** 2 for p in lookback) / Z_SCORE_LOOKBACK
        std = variance ** 0.5

        if std == 0:
            return None

        z = (prices[0] - mean) / std

        if abs(z) < SEVERITY_MEDIUM_THRESHOLD:
            return None

        anomaly_type = "zscore_spike" if z > 0 else "zscore_drop"
        severity = "high" if abs(z) >= SEVERITY_HIGH_THRESHOLD else "medium"

        logger.info(f"[ZScore] {anomaly_type} detected for {symbol}: z={z:.2f}, severity={severity}")

        return Alert(
            symbol=symbol,
            provider=provider,
            anomaly_type=anomaly_type,
            severity=severity,
            price=prices[0],
            z_score=round(z, 4),
            fast_ma=None,
            slow_ma=None,
        )

    def _check_ma_crossover(self, symbol: str, provider: str, prices: list[float]) -> Alert | None:
        """
        MA crossover/divergence detection.

        Requires at least SLOW_MA_WINDOW (20) prices. Flags when the fast MA
        (5-pt) diverges more than MA_DIVERGENCE_THRESHOLD (0.5%) from the
        slow MA (20-pt). Severity is always 'low'.

        Note: this is a divergence check, not a true crossover (which would
        require comparing previous MA values). Sufficient for Phase 3 alerting.
        """
        if len(prices) < SLOW_MA_WINDOW:
            logger.debug(f"[MACross] Not enough data for {symbol} (have {len(prices)}, need {SLOW_MA_WINDOW})")
            return None

        fast_ma = sum(prices[:FAST_MA_WINDOW]) / FAST_MA_WINDOW
        slow_ma = sum(prices[:SLOW_MA_WINDOW]) / SLOW_MA_WINDOW

        if slow_ma == 0:
            return None

        divergence = abs(fast_ma - slow_ma) / slow_ma
        if divergence <= MA_DIVERGENCE_THRESHOLD:
            return None

        logger.info(f"[MACross] Divergence detected for {symbol}: fast={fast_ma:.2f}, slow={slow_ma:.2f} ({divergence:.2%})")

        return Alert(
            symbol=symbol,
            provider=provider,
            anomaly_type="ma_crossover",
            severity="low",
            price=prices[0],
            z_score=None,
            fast_ma=round(fast_ma, 4),
            slow_ma=round(slow_ma, 4),
        )
