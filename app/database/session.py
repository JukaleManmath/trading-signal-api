from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# Sync engine — used only by the MA consumer (confluent_kafka is blocking)
# ---------------------------------------------------------------------------
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Async engine — used by the FastAPI app and polling worker
# ---------------------------------------------------------------------------
_async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
async_engine = create_async_engine(_async_url, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db