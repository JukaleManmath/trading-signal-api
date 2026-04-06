from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePortfolioRequest(BaseModel):
    name: str
    portfolio_type: str = "stock"


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    portfolio_type: str
    created_at: datetime


class AddPositionRequest(BaseModel):
    symbol: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0, description="Price per share at time of purchase")
    provider: str = "finnhub"


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    symbol: str
    provider: str
    quantity: float
    avg_cost_basis: float
    is_active: bool
    opened_at: datetime
    closed_at: datetime | None


class PositionSnapshot(BaseModel):
    position_id: UUID
    symbol: str
    provider: str
    quantity: float
    avg_cost_basis: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    pnl_pct: float
    weight: float


class PortfolioSnapshot(BaseModel):
    portfolio_id: UUID
    portfolio_name: str
    total_value: float
    total_pnl: float
    positions: list[PositionSnapshot]
