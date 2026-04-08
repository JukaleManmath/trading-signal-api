import json
import logging
import signal
import time

from confluent_kafka import Consumer, KafkaException, Producer
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.redis import redis_sync_client
from app.database.session import SessionLocal
from app.services.moving_average_service import MovingAverageService

DEDUP_TTL = 86400  # 24 hours in seconds
MAX_RETRIES = 3
DLQ_TOPIC = "price-events-dlq"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _publish_to_dlq(producer: Producer, raw_value: bytes, error: str) -> None:
    payload = json.dumps({
        "original_message": raw_value.decode("utf-8"),
        "error": error,
        "consumer": "ma-consumer",
    }).encode("utf-8")
    producer.produce(DLQ_TOPIC, value=payload)
    producer.flush()
    logger.warning(f"[MAConsumer] Message sent to DLQ: {error}")


def start_consumer():
    """
    Entry point for the ma-consumer container.

    Subscribes to the 'price-events' Kafka topic. For every message,
    delegates MA computation to MovingAverageService — this function
    owns only the Kafka loop lifecycle (connect, poll, shutdown).
    Failed messages are retried up to MAX_RETRIES times with exponential
    backoff before being published to the DLQ topic.
    """
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "ma-consumer-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    consumer.subscribe(["price-events"])
    logger.info("MA Consumer started — listening on 'price-events'")

    shutdown_requested = False

    def shutdown(sig, frame):
        nonlocal shutdown_requested
        logger.info("MA Consumer shutdown requested — will exit after current message.")
        shutdown_requested = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while not shutdown_requested:
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            data = json.loads(msg.value())
            logger.info(f"[Kafka] Received: {data}")

            raw_response_id = data.get("raw_response_id")
            if raw_response_id:
                dedup_key = f"processed:{raw_response_id}"
                already_seen = not redis_sync_client.setnx(dedup_key, "1")
                if already_seen:
                    logger.info(f"[MAConsumer] Duplicate message skipped: {raw_response_id}")
                    continue
                redis_sync_client.expire(dedup_key, DEDUP_TTL)

            last_error: Exception | None = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    db = SessionLocal()
                    try:
                        MovingAverageService(db=db).compute_and_store(
                            symbol=data["symbol"],
                            provider=data["source"],
                        )
                    finally:
                        db.close()
                    last_error = None
                    break  # success — stop retrying
                except Exception as e:
                    last_error = e
                    logger.warning(f"[MAConsumer] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(2 ** (attempt - 1))  # 1s, 2s

            if last_error is not None:
                _publish_to_dlq(producer, msg.value(), str(last_error))

        except SQLAlchemyError as e:
            logger.exception(f"[DB ERROR] {e}")
        except Exception as e:
            logger.exception(f"[Consumer ERROR] {e}")

    logger.info("MA Consumer shutting down cleanly.")
    consumer.close()
