import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.api.poll import router as poll_router
from app.api.portfolios import router as portfolios_router
from app.api.prices import router as price_router
from app.api.stream import router as stream_router
from app.api.signals import router as signal_router
from app.core.kafka_broadcaster import start_broadcaster
from app.core.logging import setup_logging
from app.kafka.producer import producer
from app.middleware.request_id import RequestIDMiddleware
from app.services.polling_worker_service import polling_worker

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(polling_worker())
    asyncio.create_task(start_broadcaster())
    yield
    producer.flush(timeout=10)


app = FastAPI(
    title="Systematic Trading Signal & Risk API",
    description="Real-time signal generation, portfolio risk monitoring, and anomaly alerting.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(health_router)
app.include_router(price_router)
app.include_router(poll_router)
app.include_router(alerts_router)
app.include_router(portfolios_router)
app.include_router(analytics_router)
app.include_router(stream_router)
app.include_router(signal_router)