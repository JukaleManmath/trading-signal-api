from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    provider: str
    anomaly_type: str
    severity: str
    price: float
    z_score: float | None
    fast_ma: float | None
    slow_ma: float | None
    resolved: bool
    timestamp: datetime
