import json
import logging

from confluent_kafka import Producer

from app.core.config import settings

logger = logging.getLogger(__name__)

_conf = {
    "bootstrap.servers": settings.kafka_bootstrap_servers,
    "client.id": "market-data-producer",
    "acks": "all",
    "retries": 5,
}

producer = Producer(**_conf)


def _delivery_report(err, msg) -> None:
    if err is not None:
        logger.error(f"[Kafka] Delivery failed: {err}")
    else:
        logger.info(f"[Kafka] Delivered to {msg.topic()} [{msg.partition()}]")


async def send_price_event(
    symbol: str,
    price: float,
    timestamp: str,
    provider: str,
    raw_response_id: str,
) -> None:
    """
    Enqueue a price event onto the Kafka producer buffer.

    produce() is non-blocking — it hands the message to confluent_kafka's
    internal buffer and returns immediately. The buffer is flushed in bulk
    on app shutdown (see main.py lifespan), not here, so we never block the
    event loop waiting for broker acknowledgement on every message.
    """
    message = {
        "symbol": symbol,
        "price": price,
        "timestamp": timestamp,
        "source": provider,
        "raw_response_id": raw_response_id,
    }
    try:
        producer.produce(
            topic="price-events",
            key=symbol,
            value=json.dumps(message),
            callback=_delivery_report,
        )
    except Exception as e:
        logger.exception(f"[Kafka] Failed to enqueue message for {symbol}: {e}")
