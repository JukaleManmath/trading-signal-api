import redis
from redis.asyncio import Redis

from app.core.config import settings

# Async client — used by FastAPI routes and services on the event loop
redis_client = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,
)

# Sync client — used by Kafka consumers (confluent_kafka is blocking)
redis_sync_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,
)
