import logging

from confluent_kafka import Consumer
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.config import settings
from app.core.metrics import CONSUMER_LAG
from app.core.redis import redis_client
from app.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

_CONSUMER_GROUPS = ["ma-consumer-group", "anomaly-consumer-group"]
_TOPIC = "price-events"


def _update_consumer_lag() -> dict[str, int]:
    """
    Query the Kafka broker for the latest offset and each consumer group's
    committed offset, compute lag, and update the Prometheus gauge.

    Returns a snapshot dict for the /health response.
    """
    lag_snapshot: dict[str, int] = {}
    try:
        admin_conf = {"bootstrap.servers": settings.kafka_bootstrap_servers}
        for group in _CONSUMER_GROUPS:
            consumer = Consumer({**admin_conf, "group.id": group})

            # Get committed offsets for this group
            topic_partitions = consumer.committed(
                [__import__("confluent_kafka").TopicPartition(_TOPIC, 0)]
            )
            committed = topic_partitions[0].offset if topic_partitions else 0

            # Get high-water mark (latest offset on broker)
            _, high = consumer.get_watermark_offsets(
                __import__("confluent_kafka").TopicPartition(_TOPIC, 0),
                timeout=2.0,
            )
            consumer.close()

            lag = max(0, high - max(0, committed))
            CONSUMER_LAG.labels(consumer_group=group, topic=_TOPIC).set(lag)
            lag_snapshot[group] = lag
    except Exception as exc:
        logger.warning("Could not fetch consumer lag: %s", exc)

    return lag_snapshot


@router.get("/health")
async def health_check() -> dict:
    checks: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.error("Postgres health check failed: %s", exc)
        checks["postgres"] = "error"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        checks["redis"] = "error"

    lag = _update_consumer_lag()

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks, "consumer_lag": lag}


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """Expose Prometheus metrics in the standard text exposition format."""
    _update_consumer_lag()
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
