"""
Portfolio risk engine.

Computes portfolio-level risk metrics using historical price data:
  - Parametric VaR (Value at Risk) at 95% confidence
  - Sharpe Ratio (annualised, risk-free rate = 0 for simplicity)
  - Max Drawdown (worst peak-to-trough decline over the lookback window)
  - Correlation matrix between all active positions

Requires at least MIN_PERIODS of price history per symbol.
All maths uses numpy / scipy.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

import numpy as np
from scipy.stats import norm
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alerts import Alert
from app.models.position import Position
from app.models.price_points import PricePoint
from app.services.webhook_service import async_dispatch_alerts

logger = logging.getLogger(__name__)

MIN_PERIODS = 30        # minimum daily price points required per symbol
RISK_FREE_RATE = 0.0    # annualised; set to e.g. 0.05 for 5%
TRADING_DAYS = 252      # annualisation factor for Sharpe
VAR_CONFIDENCE = 0.95   # 95% confidence interval
VOLATILITY_WINDOW = 20  # rolling window for volatility calculation (days)


@dataclass
class RiskResult:
    portfolio_id: str
    total_value: float
    var_1day_95: float | None           # dollar loss not exceeded 95% of the time
    sharpe_ratio: float | None
    max_drawdown: float | None          # e.g. -0.23 means -23% worst drawdown
    correlation_matrix: dict | None     # {symbol: {symbol: correlation}}
    rolling_volatility: float | None    # annualised rolling std dev of portfolio returns
    breaches: list[str] = field(default_factory=list)   # names of thresholds breached
    symbols_analysed: list[str] = field(default_factory=list)
    warning: str | None = None          # set when data is insufficient


class RiskEngine:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute(self, portfolio_id: UUID) -> RiskResult:
        positions = await self._fetch_active_positions(portfolio_id)

        if not positions:
            return RiskResult(
                portfolio_id=str(portfolio_id),
                total_value=0.0,
                var_1day_95=None,
                sharpe_ratio=None,
                max_drawdown=None,
                correlation_matrix=None,
                rolling_volatility=None,
                warning="No active positions in portfolio",
            )

        # Fetch price series for each position
        price_series: dict[str, np.ndarray] = {}
        weights: dict[str, float] = {}
        total_value = 0.0

        for pos in positions:
            prices = await self._fetch_prices(pos.symbol, pos.provider)
            if len(prices) < MIN_PERIODS:
                logger.warning(
                    "insufficient_history_for_risk",
                    extra={"symbol": pos.symbol, "count": len(prices)},
                )
                continue
            position_value = pos.quantity * float(prices[-1])
            price_series[pos.symbol] = np.array(prices, dtype=float)
            weights[pos.symbol] = position_value
            total_value += position_value

        if not price_series:
            return RiskResult(
                portfolio_id=str(portfolio_id),
                total_value=0.0,
                var_1day_95=None,
                sharpe_ratio=None,
                max_drawdown=None,
                correlation_matrix=None,
                rolling_volatility=None,
                warning=f"No position has {MIN_PERIODS}+ price points. Collect more data first.",
            )

        # Normalise weights to fractions (sum = 1)
        symbols = list(price_series.keys())
        weight_vec = np.array([weights[s] / total_value for s in symbols])

        # Align all series to the same length (use the shortest)
        min_len = min(len(price_series[s]) for s in symbols)
        returns_matrix = np.column_stack([
            self._log_returns(price_series[s][-min_len:]) for s in symbols
        ])  # shape: (min_len - 1, n_symbols)

        var_1day = self._parametric_var(returns_matrix, weight_vec, total_value)
        sharpe = self._sharpe_ratio(returns_matrix, weight_vec)
        max_dd = self._max_drawdown(returns_matrix, weight_vec)
        corr = self._correlation_matrix(returns_matrix, symbols)
        rolling_vol = self._rolling_volatility(returns_matrix, weight_vec)

        breach_alerts = await self._check_thresholds(
            portfolio_id=portfolio_id,
            total_value=total_value,
            var_1day=var_1day,
            max_dd=max_dd,
            rolling_vol=rolling_vol,
            weight_vec=weight_vec,
            symbols=symbols,
        )

        breach_names = [a.anomaly_type for a in breach_alerts]

        if breach_alerts:
            await async_dispatch_alerts(breach_alerts, self._db)

        return RiskResult(
            portfolio_id=str(portfolio_id),
            total_value=round(total_value, 2),
            var_1day_95=round(var_1day, 2),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 4),
            correlation_matrix=corr,
            rolling_volatility=round(rolling_vol, 4) if rolling_vol is not None else None,
            breaches=breach_names,
            symbols_analysed=symbols,
        )

    # ------------------------------------------------------------------ #
    # DB helpers
    # ------------------------------------------------------------------ #

    async def _fetch_active_positions(self, portfolio_id: UUID) -> list[Position]:
        result = await self._db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def _fetch_prices(self, symbol: str, provider: str) -> list[float]:
        """Fetch up to 252 most recent prices, oldest → newest."""
        result = await self._db.execute(
            select(PricePoint.price)
            .where(PricePoint.symbol == symbol, PricePoint.provider == provider)
            .order_by(desc(PricePoint.timestamp))
            .limit(252)
        )
        rows = result.scalars().all()
        return list(reversed(rows))

    # ------------------------------------------------------------------ #
    # Maths
    # ------------------------------------------------------------------ #

    def _log_returns(self, prices: np.ndarray) -> np.ndarray:
        """
        Log returns: ln(P_t / P_{t-1}).

        We use log returns (not simple returns) because they are additive over time
        and better behaved statistically for risk calculations.
        """
        return np.log(prices[1:] / prices[:-1])

    def _parametric_var(
        self,
        returns: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
    ) -> float:
        """
        Parametric (variance-covariance) VaR at VAR_CONFIDENCE level.

        Steps:
        1. Build covariance matrix of daily log returns.
        2. Portfolio variance = w^T * Cov * w  (dot products with weight vector).
        3. Portfolio std dev  = sqrt(variance).
        4. VaR = portfolio_value * z_score * std_dev.

        z_score for 95% confidence = norm.ppf(1 - 0.95) = -1.645
        The negative sign flips it to a positive dollar loss figure.
        """
        cov_matrix = np.cov(returns.T)
        if returns.shape[1] == 1:
            # Single-symbol portfolio — cov is a scalar
            portfolio_variance = float(cov_matrix) * (weights[0] ** 2)
        else:
            portfolio_variance = float(weights @ cov_matrix @ weights)

        portfolio_std = np.sqrt(portfolio_variance)
        z_score = norm.ppf(1 - VAR_CONFIDENCE)  # negative value
        return -portfolio_value * z_score * portfolio_std

    def _sharpe_ratio(self, returns: np.ndarray, weights: np.ndarray) -> float:
        """
        Sharpe Ratio = (mean_portfolio_return - risk_free_rate) / std * sqrt(252).

        Annualised by multiplying by sqrt(252) trading days.
        Higher = better risk-adjusted return.
        """
        portfolio_returns = returns @ weights
        mean_return = portfolio_returns.mean()
        std_return = portfolio_returns.std(ddof=1)

        if std_return == 0:
            return 0.0

        daily_sharpe = (mean_return - RISK_FREE_RATE / TRADING_DAYS) / std_return
        return float(daily_sharpe * np.sqrt(TRADING_DAYS))

    def _max_drawdown(self, returns: np.ndarray, weights: np.ndarray) -> float:
        """
        Maximum drawdown = worst peak-to-trough decline over the entire history.

        We reconstruct a cumulative portfolio value index starting at 1.0,
        then find the largest drop from any peak.

        Example: if the index goes 1.0 → 1.3 → 0.9, drawdown = (0.9 - 1.3) / 1.3 = -0.31 (-31%).
        """
        portfolio_returns = returns @ weights
        cumulative = np.cumprod(1 + portfolio_returns)

        # Running maximum at each point
        running_max = np.maximum.accumulate(cumulative)

        drawdowns = (cumulative - running_max) / running_max
        return float(drawdowns.min())  # most negative value = worst drawdown

    def _rolling_volatility(
        self,
        returns: np.ndarray,
        weights: np.ndarray,
    ) -> float | None:
        """
        Annualised rolling volatility of the portfolio over the last VOLATILITY_WINDOW days.

        Steps:
        1. Compute portfolio returns as weighted sum of individual returns.
        2. Take the last VOLATILITY_WINDOW observations.
        3. Std dev of that window * sqrt(252) to annualise.

        Returns None if there are fewer observations than the window size.
        """
        portfolio_returns = returns @ weights
        if len(portfolio_returns) < VOLATILITY_WINDOW:
            return None
        recent = portfolio_returns[-VOLATILITY_WINDOW:]
        return float(np.std(recent, ddof=1) * np.sqrt(TRADING_DAYS))

    async def _check_thresholds(
        self,
        portfolio_id: UUID,
        total_value: float,
        var_1day: float,
        max_dd: float,
        rolling_vol: float | None,
        weight_vec: np.ndarray,
        symbols: list[str],
    ) -> list[Alert]:
        """
        Compare computed metrics against configured thresholds.
        For each breach, persist an Alert row and return all created alerts.

        portfolio_id is stored as the alert symbol so the dashboard can filter
        risk alerts by portfolio. provider is set to 'risk_engine'.
        """
        alerts: list[Alert] = []
        portfolio_str = str(portfolio_id)
        now = datetime.now(tz=timezone.utc)

        # VaR breach: var as fraction of portfolio value exceeds threshold
        if total_value > 0 and (var_1day / total_value) > settings.risk_var_threshold:
            alert = Alert(
                id=uuid4(),
                symbol=portfolio_str,
                provider="risk_engine",
                anomaly_type="var_breach",
                severity="high",
                price=total_value,
                timestamp=now,
            )
            self._db.add(alert)
            alerts.append(alert)
            logger.warning("risk_breach_var", extra={"portfolio_id": portfolio_str, "var": var_1day})

        # Drawdown breach: max drawdown worse than threshold (more negative)
        if max_dd < settings.risk_drawdown_threshold:
            alert = Alert(
                id=uuid4(),
                symbol=portfolio_str,
                provider="risk_engine",
                anomaly_type="drawdown_breach",
                severity="high",
                price=total_value,
                timestamp=now,
            )
            self._db.add(alert)
            alerts.append(alert)
            logger.warning("risk_breach_drawdown", extra={"portfolio_id": portfolio_str, "drawdown": max_dd})

        # Concentration breach: any single position exceeds threshold weight
        for i, symbol in enumerate(symbols):
            if float(weight_vec[i]) > settings.risk_concentration_threshold:
                alert = Alert(
                    id=uuid4(),
                    symbol=portfolio_str,
                    provider="risk_engine",
                    anomaly_type="concentration_breach",
                    severity="medium",
                    price=total_value,
                    timestamp=now,
                )
                self._db.add(alert)
                alerts.append(alert)
                logger.warning(
                    "risk_breach_concentration",
                    extra={"portfolio_id": portfolio_str, "symbol": symbol, "weight": float(weight_vec[i])},
                )
                break  # one alert per portfolio compute, not per symbol

        # Volatility breach: rolling annualised volatility exceeds threshold
        if rolling_vol is not None and rolling_vol > settings.risk_volatility_threshold:
            alert = Alert(
                id=uuid4(),
                symbol=portfolio_str,
                provider="risk_engine",
                anomaly_type="volatility_breach",
                severity="medium",
                price=total_value,
                timestamp=now,
            )
            self._db.add(alert)
            alerts.append(alert)
            logger.warning("risk_breach_volatility", extra={"portfolio_id": portfolio_str, "vol": rolling_vol})

        if alerts:
            await self._db.commit()
            for alert in alerts:
                await self._db.refresh(alert)

        return alerts

    def _correlation_matrix(
        self,
        returns: np.ndarray,
        symbols: list[str],
    ) -> dict[str, dict[str, float]]:
        """
        Correlation matrix between all symbols.

        Values range from -1 (perfectly opposite) to +1 (perfectly together).
        Close to 0 = uncorrelated = better diversification.
        """
        if len(symbols) == 1:
            # np.corrcoef on a single series returns a scalar 1.0, not a matrix
            return {symbols[0]: {symbols[0]: 1.0}}

        corr = np.corrcoef(returns.T)
        return {
            symbols[i]: {
                symbols[j]: round(float(corr[i, j]), 4)
                for j in range(len(symbols))
            }
            for i in range(len(symbols))
        }
