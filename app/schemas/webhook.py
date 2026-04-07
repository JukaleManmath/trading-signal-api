from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class WebhookCreate(BaseModel):
    url: HttpUrl
    event_type: str = "alert.created"
    symbol: str | None = None
    min_severity: str | None = None
    secret: str | None = None


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    event_type: str
    symbol: str | None
    min_severity: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
