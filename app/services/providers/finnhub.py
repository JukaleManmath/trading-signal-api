import asyncio
import json
import logging
from datetime import datetime

import httpx
from fastapi import HTTPException

from app.services.providers.base import BaseProvider, PriceFetchResult

logger = logging.getLogger(__name__)

FINNHUB_URL = "https://finnhub.io/api/v1/quote"
MAX_RETRIES = 3


class FinnhubProvider(BaseProvider):
    """
    Fetches real-time quotes from the Finnhub REST API.

    Each instance holds its own API key so the key is injected at
    construction time (from the registry) rather than read from
    settings directly inside fetch() — Dependency Inversion Principle.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "finnhub"

    async def fetch(self, symbol: str) -> PriceFetchResult:
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        FINNHUB_URL,
                        params={"symbol": symbol, "token": self._api_key},
                    )
                    response.raise_for_status()
                    data = response.json()

                if "c" not in data or data["c"] == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Symbol '{symbol}' not found on Finnhub",
                    )

                logger.info(f"[Finnhub] Fetched {symbol}: {data}")
                return PriceFetchResult(
                    symbol=symbol,
                    price=float(data["c"]),
                    timestamp=datetime.utcfromtimestamp(data["t"]),
                    provider=self.name,
                    raw_json=json.dumps(data),
                )

            except HTTPException:
                raise  # don't retry on 404
            except Exception as e:
                logger.warning(f"[Finnhub] Attempt {attempt + 1}/{MAX_RETRIES} failed for {symbol}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=503, detail="Finnhub provider unavailable")
                await asyncio.sleep(2 ** attempt)
