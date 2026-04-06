import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)


async def start_broadcaster() -> None:
    """
    Background asyncio task that reads price-events from Kafka and
    broadcasts each tick to all WebSocket clients watching that symbol.

    Uses aiokafka (async) so it runs inside the FastAPI event loop and
    can call `await manager.broadcast()` without blocking.
    """
    consumer = AIOKafkaConsumer(
        "price-events",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="websocket-broadcaster",
        auto_offset_reset="latest",  # only new messages — don't replay history on connect
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    await consumer.start()
    logger.info("kafka_broadcaster_started")

    try:
        async for msg in consumer:
            data: dict = msg.value
            symbol: str = data.get("symbol", "")
            if not symbol:
                continue

            payload = {
                "symbol": symbol,
                "price": data.get("price"),
                "timestamp": data.get("timestamp"),
                "provider": data.get("source"),
            }

            await manager.broadcast(symbol, payload)

    except asyncio.CancelledError:
        logger.info("kafka_broadcaster_stopping")
    finally:
        await consumer.stop()
        logger.info("kafka_broadcaster_stopped")
