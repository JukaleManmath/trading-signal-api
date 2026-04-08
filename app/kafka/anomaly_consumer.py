import json
import logging
import signal
import time

from confluent_kafka import Consumer, KafkaException, Producer
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.redis import redis_sync_client
from app.database.session import SessionLocal
from app.services.anomaly_detector import AnomalyDetector
from app.services.webhook_service import dispatch_alerts

DEDUP_TTL = 86400  # 24 hours in seconds
MAX_RETRIES = 3
DLQ_TOPIC = "price-events-dlq"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _publish_to_dlq(producer: Producer, raw_value: bytes, error: str) -> None:
    payload = json.dumps({
        "original_message": raw_value.decode("utf-8"),
        "error": error,
        "consumer": "anomaly-consumer",
    }).encode("utf-8")
    producer.produce(DLQ_TOPIC, value=payload)
    producer.flush()
    logger.warning(f"[AnomalyConsumer] Message sent to DLQ: {error}")


def start_consumer() -> None:
    """
    Entry point for the anomaly-consumer container.

    Subscribes to the 'price-events' Kafka topic using a separate consumer
    group ('anomaly-consumer-group') so it receives every message independently
    of the MA consumer. For each message, delegates anomaly detection to
    AnomalyDetector — this function owns only the Kafka loop lifecycle
    (connect, poll, shutdown). Business logic stays in the service class.
    Failed messages are retried up to MAX_RETRIES times with exponential
    backoff before being published to the DLQ topic.
    """
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "anomaly-consumer-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    consumer.subscribe(["price-events"])
    logger.info("Anomaly Consumer started — listening on 'price-events'")

    shutdown_requested = False

    def shutdown(sig, frame):
        nonlocal shutdown_requested
        logger.info("Anomaly Consumer shutdown requested — will exit after current message.")
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
            logger.info(f"[AnomalyConsumer] Received: {data}")

            raw_response_id = data.get("raw_response_id")
            if raw_response_id:
                dedup_key = f"processed:{raw_response_id}"
                already_seen = not redis_sync_client.setnx(dedup_key, "1")
                if already_seen:
                    logger.info(f"[AnomalyConsumer] Duplicate message skipped: {raw_response_id}")
                    continue
                redis_sync_client.expire(dedup_key, DEDUP_TTL)

            last_error: Exception | None = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    db = SessionLocal()
                    try:
                        alerts = AnomalyDetector(db=db).detect_and_store(
                            symbol=data["symbol"],
                            provider=data["source"],
                        )
                        if alerts:
                            logger.info(f"[AnomalyConsumer] {len(alerts)} alert(s) stored for {data['symbol']}")
                            dispatch_alerts(alerts, db)
                    finally:
                        db.close()
                    last_error = None
                    break  # success — stop retrying
                except Exception as e:
                    last_error = e
                    logger.warning(f"[AnomalyConsumer] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(2 ** (attempt - 1))  # 1s, 2s

            if last_error is not None:
                _publish_to_dlq(producer, msg.value(), str(last_error))

        except SQLAlchemyError as e:
            logger.exception(f"[AnomalyConsumer DB ERROR] {e}")
        except Exception as e:
            logger.exception(f"[AnomalyConsumer ERROR] {e}")

    logger.info("Anomaly Consumer shutting down cleanly.")
    consumer.close()
