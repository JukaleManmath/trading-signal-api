from fastapi import HTTPException

from app.core.config import settings
from app.services.providers.base import BaseProvider
from app.services.providers.finnhub import FinnhubProvider
from app.services.providers.alpha_vantage import AlphaVantageProvider
from app.services.providers.binance import BinanceProvider

# Add a new data source by:
#   1. Creating a new subclass of BaseProvider
#   2. Adding one line here — nothing else changes
_PROVIDERS: dict[str, BaseProvider] = {
    "finnhub": FinnhubProvider(api_key=settings.finnhub_api_key),
    "alpha_vantage": AlphaVantageProvider(api_key=settings.alpha_vantage_api_key),
    "binance": BinanceProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """
    Resolve a provider name string to its implementation instance.

    Raises HTTP 400 for unknown provider names so the error surfaces
    clearly at the API layer rather than crashing deep in PriceService.
    """
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{name}'. Available: {list(_PROVIDERS.keys())}",
        )
    return provider
