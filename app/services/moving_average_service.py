import logging

from sqlalchemy.orm import Session

from app.models.moving_average import MovingAverage
from app.models.price_points import PricePoint

logger = logging.getLogger(__name__)

MA_WINDOW = 5  # number of data points for the moving average


class MovingAverageService:
    """
    Computes and persists the N-point moving average for a symbol.

    Single responsibility: MA calculation + deduplication.
    Completely decoupled from Kafka — the consumer calls this after
    receiving a message; this class doesn't know or care about Kafka.

    DB session is injected at construction time (Dependency Inversion),
    making it easy to swap in a test session.
    """

    def __init__(self, db: Session):
        self.db = db

    def compute_and_store(self, symbol: str, provider: str) -> None:
        """
        Fetch the last MA_WINDOW price points, compute the average, and
        persist a MovingAverage row — skipping if one already exists for
        that timestamp (idempotent / safe to call multiple times).
        """
        rows = (
            self.db.query(PricePoint)
            .filter_by(symbol=symbol)
            .order_by(PricePoint.timestamp.desc())
            .limit(MA_WINDOW)
            .all()
        )

        if len(rows) < MA_WINDOW:
            logger.info(f"[MA] Not enough data for {symbol} (have {len(rows)}, need {MA_WINDOW})")
            return

        avg_price = sum(r.price for r in rows) / MA_WINDOW
        latest_ts = max(r.timestamp for r in rows)

        already_exists = self.db.query(MovingAverage).filter_by(
            symbol=symbol,
            interval=MA_WINDOW,
            timestamp=latest_ts,
            provider=provider,
        ).first()

        if already_exists:
            logger.info(f"[MA] Already recorded for {symbol} @ {latest_ts}")
            return

        self.db.add(MovingAverage(
            symbol=symbol,
            average_price=avg_price,
            interval=MA_WINDOW,
            provider=provider,
            timestamp=latest_ts,
        ))
        self.db.commit()
        logger.info(f"[MA] Saved {symbol} avg={avg_price:.2f} @ {latest_ts}")
