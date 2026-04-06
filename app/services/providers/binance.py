import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from app.services.providers.base import BaseProvider, PriceFetchResult

logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.us/api/v3/ticker/price"
MAX_RETRIES = 3


class BinanceProvider(BaseProvider):
    """
    Fetches real-time crypto prices from the Binance public REST API.

    No API key required — Binance public endpoints are free and unauthenticated.
    Symbols are stored internally as e.g. 'BTC' and the provider appends 'USDT'
    to form the Binance trading pair (BTCUSDT).
    """

    @property
    def name(self) -> str:
        return "binance"

    async def fetch(self, symbol: str) -> PriceFetchResult:
        binance_symbol = f"{symbol.upper()}USDT"

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        BINANCE_URL,
                        params={"symbol": binance_symbol},
                    )
                    if response.status_code == 400:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Symbol '{symbol}' not found on Binance (tried {binance_symbol})",
                        )
                    response.raise_for_status()
                    data = response.json()

                price = float(data["price"])
                if price <= 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Invalid price returned for '{symbol}'",
                    )

                logger.info("[Binance] Fetched %s: %s", binance_symbol, price)
                return PriceFetchResult(
                    symbol=symbol.upper(),
                    price=price,
                    timestamp=datetime.now(tz=timezone.utc),
                    provider=self.name,
                    raw_json=json.dumps(data),
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.warning(
                    "[Binance] Attempt %d/%d failed for %s: %s",
                    attempt + 1, MAX_RETRIES, binance_symbol, e,
                )
                if attempt == MAX_RETRIES - 1:
                    raise HTTPException(status_code=503, detail="Binance provider unavailable")
                await asyncio.sleep(2 ** attempt)
