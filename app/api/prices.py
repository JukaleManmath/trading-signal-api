from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.database.session import get_async_db
from app.models.price_points import PricePoint
from app.schemas.price import PriceHistoryItem, PriceResponse
from app.services.price_service import PriceService
from app.services.providers.registry import get_provider

router = APIRouter(prefix="/prices", tags=["Prices"])


@router.get("/latest", status_code=status.HTTP_200_OK, response_model=PriceResponse)
async def get_latest_price(
    symbol: str,
    provider: str = "finnhub",
    db: AsyncSession = Depends(get_async_db),
):
    service = PriceService(
        provider=get_provider(provider),
        db=db,
        cache=redis_client,
    )
    return await service.get_latest_price(symbol, publish_to_kafka=True)


@router.get("/history", response_model=list[PriceHistoryItem])
async def get_price_history(
    symbol: str,
    provider: str = "finnhub",
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db),
) -> list[PriceHistoryItem]:
    symbol = symbol.upper()
    result = await db.execute(
        select(PricePoint.price, PricePoint.timestamp, PricePoint.provider)
        .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
        .order_by(asc(PricePoint.timestamp))
        .limit(limit)
    )
    rows = result.all()
    return [PriceHistoryItem(price=r.price, timestamp=r.timestamp, provider=r.provider) for r in rows]
