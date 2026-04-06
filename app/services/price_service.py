import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.kafka.producer import send_price_event
from app.models.price_points import PricePoint
from app.models.raw_market_data import RawMarketData
from app.services.providers.base import BaseProvider, PriceFetchResult

logger = logging.getLogger(__name__)


class PriceService:
    """
    Orchestrates the 3-tier price lookup pipeline.

    Tier 1 — Redis cache  (fastest, TTL-bounded)
    Tier 2 — PostgreSQL   (recent price_points within freshness window)
    Tier 3 — External API (via injected BaseProvider)

    All dependencies (provider, db session, cache client) are injected at
    construction time — Dependency Inversion Principle. This makes the class
    testable and keeps it decoupled from concrete infrastructure.

    Instantiated per-request (or per-poll-tick) because the DB session is
    request-scoped. Phase 2 will swap Session → AsyncSession and
    redis.Redis → redis.asyncio.Redis without changing this class's structure.
    """

    def __init__(self, provider: BaseProvider, db: AsyncSession, cache: Redis):
        self.provider = provider
        self.db = db
        self.cache = cache
        self._freshness = timedelta(seconds=settings.db_price_ttl or 60)

    # ------------------------------------------------------------------
    # Private helpers — each has exactly one job (Single Responsibility)
    # ------------------------------------------------------------------

    def _cache_key(self, symbol: str) -> str:
        return f"{symbol.lower()}:{self.provider.name}"

    async def _get_from_cache(self, symbol: str) -> dict | None:
        """Return a fresh cached price dict, or None if missing/stale."""
        raw = await self.cache.get(self._cache_key(symbol))
        if not raw:
            return None

        data = json.loads(raw)
        cached_time = datetime.fromisoformat(data["timestamp"])
        if datetime.utcnow() - cached_time < self._freshness:
            logger.info(f"[CACHE HIT] {symbol}")
            return data

        logger.info(f"[CACHE STALE] {symbol}")
        return None

    async def _get_from_db(self, symbol: str) -> dict | None:
        """Return the most recent price from DB if within the freshness window."""
        stmt = (
            select(PricePoint)
            .where(
                PricePoint.symbol == symbol,
                PricePoint.provider == self.provider.name,
                PricePoint.timestamp >= datetime.utcnow() - self._freshness,
            )
            .order_by(PricePoint.timestamp.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None

        logger.info(f"[DB HIT] {symbol}")
        price_dict = self._build_result_dict(symbol, row.price, row.timestamp)
        await self._write_to_cache(symbol, price_dict)
        return price_dict

    async def _persist(self, fetch_result: PriceFetchResult) -> str:
        """
        Write RawMarketData + PricePoint to the DB.
        Returns the raw_data_id string (needed for the Kafka event).
        """
        raw_entry = RawMarketData(
            id=uuid4(),
            symbol=fetch_result.symbol,
            provider=fetch_result.provider,
            raw_json=fetch_result.raw_json,
            timestamp=datetime.utcnow(),
        )
        self.db.add(raw_entry)
        await self.db.commit()
        await self.db.refresh(raw_entry)

        self.db.add(PricePoint(
            symbol=fetch_result.symbol,
            provider=fetch_result.provider,
            price=fetch_result.price,
            timestamp=fetch_result.timestamp,
            raw_data_id=raw_entry.id,
        ))
        await self.db.commit()
        logger.info(f"[DB] Stored price point for {fetch_result.symbol} @ {fetch_result.timestamp}")

        return str(raw_entry.id)

    async def _write_to_cache(self, symbol: str, data: dict) -> None:
        await self.cache.setex(self._cache_key(symbol), int(self._freshness.total_seconds()), json.dumps(data))
        logger.info(f"[CACHE SET] {symbol}")

    async def _publish_to_kafka(self, fetch_result: PriceFetchResult, raw_data_id: str) -> None:
        """Fire a price event to Kafka. Failures are logged but non-fatal."""
        try:
            await send_price_event(
                symbol=fetch_result.symbol,
                price=fetch_result.price,
                timestamp=fetch_result.timestamp.isoformat(),
                provider=fetch_result.provider,
                raw_response_id=raw_data_id,
            )
            logger.info(f"[KAFKA] Event sent for {fetch_result.symbol}")
        except Exception as e:
            logger.error(f"[KAFKA ERROR] Failed to send event for {fetch_result.symbol}: {e}")

    def _build_result_dict(self, symbol: str, price: float, timestamp: datetime) -> dict:
        return {
            "symbol": symbol,
            "price": price,
            "timestamp": timestamp.isoformat(),
            "provider": self.provider.name,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_latest_price(self, symbol: str, publish_to_kafka: bool = False) -> dict:
        """
        Return the latest price for a symbol via the 3-tier lookup chain.

        Cache and DB hits return immediately without touching external APIs
        or firing Kafka events. Only a Tier 3 (external API) fetch triggers
        persistence and optionally a Kafka event.
        """
        # Tier 1: Redis cache
        result = await self._get_from_cache(symbol)
        if result:
            return result

        # Tier 2: DB (recent price_points)
        result = await self._get_from_db(symbol)
        if result:
            return result

        # Tier 3: external API via injected provider
        fetch_result = await self.provider.fetch(symbol)
        raw_data_id = await self._persist(fetch_result)
        result = self._build_result_dict(symbol, fetch_result.price, fetch_result.timestamp)
        await self._write_to_cache(symbol, result)

        if publish_to_kafka:
            await self._publish_to_kafka(fetch_result, raw_data_id)

        return result
