from redis.asyncio import Redis

from app.core.config import settings

redis_client = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,
)
