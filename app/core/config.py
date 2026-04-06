from pydantic import model_validator
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

    # ------------------------------------------------------------------
    # Signal generator weights — one set per strategy mode.
    #
    # In production quant systems these are NOT hand-picked. They are
    # derived by backtesting: run the strategy over years of historical
    # data, compute the Information Coefficient (IC) of each indicator
    # (how well it predicts next-period returns), and assign weights
    # proportional to IC strength. Optimise for Sharpe ratio.
    #
    # Here we use reasonable starting defaults that reflect each
    # indicator's natural role in each regime. Override via .env to
    # tune without touching code — the model_validator below enforces
    # that weights sum to 1.0 on startup so misconfiguration fails fast.
    # ------------------------------------------------------------------

    # Trend-following: momentum indicators carry more weight.
    # Rationale: MACD and EMA directly measure trend direction and
    # strength; OBV confirms whether volume supports the move.
    tf_weight_macd: float = 0.30
    tf_weight_ema: float = 0.25
    tf_weight_obv: float = 0.20
    tf_weight_rsi: float = 0.15
    tf_weight_bollinger: float = 0.10

    # Mean-reversion: RSI and Bollinger dominate because they measure
    # how far price has stretched from its statistical baseline.
    # OBV is near-zero — volume confirmation matters less in ranging markets.
    mr_weight_rsi: float = 0.35
    mr_weight_bollinger: float = 0.35
    mr_weight_macd: float = 0.15
    mr_weight_ema: float = 0.10
    mr_weight_obv: float = 0.05

    # Caution: weights are more balanced and the HOLD threshold is higher
    # (see SignalGenerator). No single indicator dominates — all must
    # broadly agree before a directional signal fires.
    ca_weight_bollinger: float = 0.30
    ca_weight_rsi: float = 0.25
    ca_weight_macd: float = 0.20
    ca_weight_ema: float = 0.15
    ca_weight_obv: float = 0.10

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> "Settings":
        tolerance = 1e-6
        strategies = {
            "trend-following": (
                self.tf_weight_macd + self.tf_weight_ema + self.tf_weight_obv
                + self.tf_weight_rsi + self.tf_weight_bollinger
            ),
            "mean-reversion": (
                self.mr_weight_rsi + self.mr_weight_bollinger + self.mr_weight_macd
                + self.mr_weight_ema + self.mr_weight_obv
            ),
            "caution": (
                self.ca_weight_bollinger + self.ca_weight_rsi + self.ca_weight_macd
                + self.ca_weight_ema + self.ca_weight_obv
            ),
        }
        for mode, total in strategies.items():
            if abs(total - 1.0) > tolerance:
                raise ValueError(
                    f"Signal weights for strategy '{mode}' must sum to 1.0, got {total:.6f}. "
                    f"Check your .env configuration."
                )
        return self


settings = Settings()
