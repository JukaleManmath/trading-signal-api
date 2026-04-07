import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_db
from app.models.price_points import PricePoint
from app.schemas.analytics import IndicatorResponse, RiskResponse
from app.services.risk_engine import RiskEngine
from app.services.signal_generator import SignalGenerator, StrategyMode
from app.services.technical_analysis import TechnicalAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{symbol}/indicators", response_model=IndicatorResponse)
async def get_indicators(
    symbol: str,
    provider: str = Query(default="finnhub"),
    strategy: StrategyMode = Query(default=StrategyMode.TREND_FOLLOWING),
    db: AsyncSession = Depends(get_async_db),
) -> IndicatorResponse:
    """
    Compute RSI, MACD, Bollinger, EMA, SMA, ADX, OBV for a symbol, then generate a signal.

    strategy: trend-following | mean-reversion | caution (default: trend-following)

    Requires at least 35 price points for full MACD. RSI needs 15, Bollinger/EMA/SMA need 20,
    ADX needs 15 with H/L data, OBV needs 2 with volume data. Insufficient indicators return null.
    """
    symbol = symbol.upper()

    ta_service = TechnicalAnalysisService(db)
    indicators = await ta_service.compute(symbol, provider)

    if indicators.price_count == 0:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol} / {provider}")

    # Get the latest price for Bollinger band comparison
    current_price = 0.0
    if indicators.bollinger is not None:
        current_price = indicators.bollinger.middle  # fallback; will be overridden below

    # Fetch the actual latest price from the DB
    result = await db.execute(
        select(PricePoint.price)
        .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
        .order_by(desc(PricePoint.timestamp))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is not None:
        current_price = float(latest)

    signal_result = SignalGenerator().generate(indicators, current_price, strategy)

    return IndicatorResponse(
        symbol=symbol,
        provider=provider,
        rsi=indicators.rsi,
        macd=(
            {"line": indicators.macd.line, "signal": indicators.macd.signal, "histogram": indicators.macd.histogram}
            if indicators.macd else None
        ),
        bollinger=(
            {
                "upper": indicators.bollinger.upper,
                "middle": indicators.bollinger.middle,
                "lower": indicators.bollinger.lower,
                "bandwidth": indicators.bollinger.bandwidth,
            }
            if indicators.bollinger else None
        ),
        ema=indicators.ema,
        sma=indicators.sma,
        adx=indicators.adx,
        obv=indicators.obv,
        signal=signal_result.signal.value,
        confidence=signal_result.confidence,
        reasons=signal_result.reasons,
        price_count=indicators.price_count,
    )


@router.get("/portfolios/{portfolio_id}/risk", response_model=RiskResponse)
async def get_portfolio_risk(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> RiskResponse:
    """
    Compute portfolio-level risk metrics: VaR, Sharpe Ratio, Max Drawdown, Correlation Matrix.

    Requires at least 30 price points per symbol. Positions with insufficient history are skipped.
    """
    engine = RiskEngine(db)
    result = await engine.compute(portfolio_id)

    return RiskResponse(
        portfolio_id=result.portfolio_id,
        total_value=result.total_value,
        var_1day_95=result.var_1day_95,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        correlation_matrix=result.correlation_matrix,
        rolling_volatility=result.rolling_volatility,
        breaches=result.breaches,
        symbols_analysed=result.symbols_analysed,
        warning=result.warning,
    )
