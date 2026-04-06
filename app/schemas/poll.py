from pydantic import BaseModel


class PollingRequest(BaseModel):
    symbols: list[str]
    interval: int
    provider: str

class PollingConfig(BaseModel):
    symbols: list[str]
    interval: int

class PollingResponse(BaseModel):
    job_id: str
    status: str
    config: PollingConfig