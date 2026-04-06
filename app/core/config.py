from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    alpha_vantage_api_key: str
    finnhub_api_key: str
    redis_host: str
    redis_port: int
    db_price_ttl: int
    kafka_bootstrap_servers: str
    redis_url: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    class Config:
        env_file = ".env"


settings = Settings()
