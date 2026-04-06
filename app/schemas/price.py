from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PriceResponse(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
    provider: str


class PriceHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price: float
    timestamp: datetime
    provider: str

