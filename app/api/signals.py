import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_db
from app.models.price_points import PricePoint
from app.models.signal_history import SignalHistory
from app.schemas.signal import SignalHistoryItem, SignalResponse
from app.services.signal_generator import SignalGenerator, StrategyMode
from app.services.technical_analysis import TechnicalAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/{symbol}", response_model=SignalResponse)
async def get_signal(
    symbol: str,
    provider: str = Query(default="finnhub"),
    strategy: StrategyMode = Query(default=StrategyMode.TREND_FOLLOWING),
    db: AsyncSession = Depends(get_async_db),
) -> SignalResponse:
    """
    Compute and persist a BUY/SELL/HOLD signal for a symbol.

    Unlike the analytics endpoint, this records every call to signal_history
    so signal changes can be tracked over time.
    """
    symbol = symbol.upper()

    indicators = await TechnicalAnalysisService(db).compute(symbol, provider)

    if indicators.price_count == 0:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol} / {provider}")

    # Fetch latest price for Bollinger/EMA comparison and for storing in history.
    result = await db.execute(
        select(PricePoint.price)
        .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
        .order_by(desc(PricePoint.timestamp))
        .limit(1)
    )
    current_price = result.scalar_one_or_none()
    if current_price is None:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol} / {provider}")
    current_price = float(current_price)

    signal_result = SignalGenerator().generate(indicators, current_price, strategy)

    # Persist to signal_history — every call is recorded.
    row = SignalHistory(
        id=uuid4(),
        symbol=symbol,
        provider=provider,
        signal=signal_result.signal.value,
        confidence=signal_result.confidence,
        weighted_score=signal_result.weighted_score,
        strategy_mode=signal_result.strategy_mode,
        price=current_price,
        rsi=indicators.rsi,
        macd_histogram=indicators.macd.histogram if indicators.macd else None,
        adx=indicators.adx,
        timestamp=datetime.now(tz=timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    logger.info("signal_persisted", extra={"symbol": symbol, "signal": signal_result.signal.value})

    return SignalResponse(
        symbol=symbol,
        provider=provider,
        signal=signal_result.signal.value,
        confidence=signal_result.confidence,
        weighted_score=signal_result.weighted_score,
        strategy_mode=signal_result.strategy_mode,
        price=current_price,
        rsi=indicators.rsi,
        macd_histogram=indicators.macd.histogram if indicators.macd else None,
        adx=indicators.adx,
        timestamp=row.timestamp,
    )


@router.get("/{symbol}/history", response_model=list[SignalHistoryItem])
async def get_signal_history(
    symbol: str,
    provider: str = Query(default="finnhub"),
    strategy: StrategyMode | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
) -> list[SignalHistoryItem]:
    """
    Return past signals for a symbol ordered newest first.

    Optionally filter by strategy mode. Limit 1–200, default 50.
    """
    symbol = symbol.upper()

    stmt = (
        select(SignalHistory)
        .where(SignalHistory.symbol == symbol, SignalHistory.provider == provider)
        .order_by(desc(SignalHistory.timestamp))
        .limit(limit)
    )
    if strategy is not None:
        stmt = stmt.where(SignalHistory.strategy_mode == strategy.value)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        SignalHistoryItem(
            id=str(row.id),
            signal=row.signal,
            confidence=row.confidence,
            weighted_score=row.weighted_score,
            strategy_mode=row.strategy_mode,
            price=row.price,
            rsi=row.rsi,
            macd_histogram=row.macd_histogram,
            adx=row.adx,
            timestamp=row.timestamp,
        )
        for row in rows
    ]
