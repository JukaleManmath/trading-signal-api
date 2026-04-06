import asyncio
import json
import logging
from datetime import datetime

import httpx
from fastapi import HTTPException

from app.services.providers.base import BaseProvider, PriceFetchResult

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
MAX_RETRIES = 3


class AlphaVantageProvider(BaseProvider):
    """
    Fetches intraday quotes from the Alpha Vantage REST API.

    API key is injected at construction time (from the registry)
    rather than read from settings inside fetch() — Dependency Inversion Principle.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "alpha_vantage"

    async def fetch(self, symbol: str) -> PriceFetchResult:
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        ALPHA_VANTAGE_URL,
                        params={
                            "function": "TIME_SERIES_INTRADAY",
                            "symbol": symbol,
                            "interval": "1min",
                            "apikey": self._api_key,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

                if "Time Series (1min)" not in data:
                    raise HTTPException(
                        status_code=404,
                        detail="Symbol not found or Alpha Vantage API limit exceeded",
                    )

                time_series = data["Time Series (1min)"]
                latest_ts_str = max(time_series.keys())
                latest = time_series[latest_ts_str]

                logger.info(f"[AlphaVantage] Fetched {symbol} @ {latest_ts_str}")
                return PriceFetchResult(
                    symbol=symbol,
                    price=float(latest["4. close"]),
                    timestamp=datetime.strptime(latest_ts_str, "%Y-%m-%d %H:%M:%S"),
                    provider=self.name,
                    raw_json=json.dumps(data),
                )

            except HTTPException:
                raise  # don't retry on 404
            except Exception as e:
                logger.warning(f"[AlphaVantage] Attempt {attempt + 1}/{MAX_RETRIES} failed for {symbol}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=503, detail="Alpha Vantage provider unavailable")
                await asyncio.sleep(2 ** attempt)
