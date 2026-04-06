from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceFetchResult:
    """
    Structured result returned by any BaseProvider.fetch() call.

    Using a dataclass (not a raw dict) gives type safety between the provider
    layer and PriceService — no string-key lookups, no silent KeyErrors.
    """
    symbol: str
    price: float
    timestamp: datetime   # already parsed — providers own the format conversion
    provider: str
    raw_json: str         # serialised raw API response, stored in raw_market_data


class BaseProvider(ABC):
    """
    Abstract contract that every price data provider must satisfy.

    To add a new data source (e.g. Polygon.io):
      1. Subclass BaseProvider
      2. Implement `name` and `fetch`
      3. Register the instance in providers/registry.py

    No existing code needs to change — that is the Open/Closed Principle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Canonical string identifier for this provider (e.g. 'finnhub').
        Used as the DB column value and the Redis cache key segment.
        """
        ...

    @abstractmethod
    async def fetch(self, symbol: str) -> PriceFetchResult:
        """
        Fetch the latest price for a symbol from the external API.

        Responsibilities:
          - HTTP call with retries and exponential backoff
          - Parse the API response into a PriceFetchResult

        Must NOT touch the DB, Redis, or Kafka — those are PriceService concerns.

        Raises:
          HTTPException(404) — symbol not found in the API response
          HTTPException(503) — all retry attempts exhausted
        """
        ...
