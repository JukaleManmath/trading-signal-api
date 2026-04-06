import json
import logging
import signal
import sys

from confluent_kafka import Consumer, KafkaException
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.anomaly_detector import AnomalyDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_consumer() -> None:
    """
    Entry point for the anomaly-consumer container.

    Subscribes to the 'price-events' Kafka topic using a separate consumer
    group ('anomaly-consumer-group') so it receives every message independently
    of the MA consumer. For each message, delegates anomaly detection to
    AnomalyDetector — this function owns only the Kafka loop lifecycle
    (connect, poll, shutdown). Business logic stays in the service class.
    """
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "anomaly-consumer-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)
    consumer.subscribe(["price-events"])
    logger.info("Anomaly Consumer started — listening on 'price-events'")

    def shutdown(sig, frame):
        logger.info("Shutting down anomaly consumer...")
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
            logger.info(f"[AnomalyConsumer] Received: {data}")

            db = SessionLocal()
            try:
                alerts = AnomalyDetector(db=db).detect_and_store(
                    symbol=data["symbol"],
                    provider=data["source"],
                )
                if alerts:
                    logger.info(f"[AnomalyConsumer] {len(alerts)} alert(s) stored for {data['symbol']}")
            finally:
                db.close()

        except SQLAlchemyError as e:
            logger.exception(f"[AnomalyConsumer DB ERROR] {e}")
        except Exception as e:
            logger.exception(f"[AnomalyConsumer ERROR] {e}")
