import json
import logging
import signal
import sys

from confluent_kafka import Consumer, KafkaException
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.moving_average_service import MovingAverageService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_consumer():
    """
    Entry point for the ma-consumer container.

    Subscribes to the 'price-events' Kafka topic. For every message,
    delegates MA computation to MovingAverageService — this function
    owns only the Kafka loop lifecycle (connect, poll, shutdown).
    """
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "ma-consumer-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)
    consumer.subscribe(["price-events"])
    logger.info("MA Consumer started — listening on 'price-events'")

    def shutdown(sig, frame):
        logger.info("Shutting down MA consumer...")
        consumer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        try:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            data = json.loads(msg.value())
            logger.info(f"[Kafka] Received: {data}")

            db = SessionLocal()
            try:
                MovingAverageService(db=db).compute_and_store(
                    symbol=data["symbol"],
                    provider=data["source"],
                )
            finally:
                db.close()

        except SQLAlchemyError as e:
            logger.exception(f"[DB ERROR] {e}")
        except Exception as e:
            logger.exception(f"[Consumer ERROR] {e}")
