# Systematic Trading Signal & Risk API

A backend platform for real-time trading signal generation, portfolio risk monitoring, and anomaly alerting — built as the intelligence layer between market data providers and trading strategies.

---

## What It Does

- Ingests live price data from Finnhub, Alpha Vantage, and Binance US
- Streams events through Kafka into an async processing pipeline
- Generates composite BUY / SELL / HOLD signals using technical indicators with configurable weighted scoring
- Computes portfolio-level risk metrics (VaR, Sharpe Ratio, drawdown, rolling volatility)
- Detects price anomalies via Z-score and moving average divergence
- Fires webhook alerts on anomalies and risk threshold breaches
- Exposes all data via REST and WebSocket APIs
- Provides an operator dashboard built in Streamlit

---

## Architecture

```
Market Data Providers (Finnhub, Alpha Vantage, Binance US)
        |
Ingestion Layer — FastAPI async polling workers
        |
Kafka  (price-events topic)
        |
        +-- MA Consumer        --> PostgreSQL
        +-- Anomaly Consumer   --> PostgreSQL + Webhook Dispatcher --> Registered Webhooks

PostgreSQL (partitioned by month)
        ^-- Signal Engine    (on-demand via API, persists to signal_history)
        ^-- Risk Engine      (on-demand via API, fires breach alerts)

Redis   (TTL cache + consumer dedup)

REST API + WebSocket API + Webhook delivery

Streamlit Operator Dashboard
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn, WebSockets |
| ORM | SQLAlchemy (async) |
| Database | PostgreSQL 15 (partitioned tables) |
| Cache | Redis 7 |
| Messaging | Apache Kafka (confluent-kafka, aiokafka) |
| Numerics | NumPy, SciPy |
| HTTP client | httpx (async webhook delivery) |
| Dashboard | Streamlit |
| Metrics | Prometheus client |
| Infrastructure | Docker Compose |

---

## Signal Engine

Signals are generated using a weighted composite scoring model across five indicators:

| Indicator | Trend-Following | Mean-Reversion | Caution |
|---|:-:|:-:|:-:|
| MACD | 0.30 | 0.15 | 0.20 |
| EMA | 0.25 | 0.10 | 0.15 |
| OBV | 0.20 | 0.05 | 0.10 |
| RSI | 0.15 | 0.35 | 0.25 |
| Bollinger Bands | 0.10 | 0.35 | 0.30 |

ADX acts as a regime modifier — it amplifies signals in trending markets and dampens them in ranging markets. Weights are configurable via environment variables and validated to sum to 1.0 on startup.

**Output:**
```json
{
  "symbol": "AAPL",
  "signal": "BUY",
  "confidence": 0.74,
  "strategy_mode": "trend-following",
  "indicators": {
    "macd": 0.65,
    "ema": 0.80,
    "obv": 0.70,
    "rsi": 0.55,
    "bollinger": 0.60
  },
  "timestamp": "2026-04-07T10:30:00Z"
}
```

---

## Risk Metrics

| Metric | Description |
|---|---|
| Parametric VaR (95%) | Expected worst-case loss at 95% confidence |
| Sharpe Ratio | Risk-adjusted return |
| Max Drawdown | Largest peak-to-trough loss in history |
| Rolling Volatility | 20-day annualised standard deviation |
| Correlation Matrix | Asset interdependence across portfolio |

Risk threshold breaches automatically create alerts and dispatch webhooks.

---

## API Reference

### Prices
```
GET  /prices/latest?symbol=AAPL&provider=finnhub
GET  /prices/history?symbol=AAPL&provider=finnhub
POST /prices/poll          body: { symbols, provider, interval }
DEL  /prices/poll/{job_id}
WS   /ws/prices/{symbol}
```

### Signals
```
GET /signals/{symbol}?strategy=trend-following
GET /signals/{symbol}/history
```

### Analytics
```
GET /analytics/{symbol}/indicators?strategy=trend-following
GET /analytics/portfolios/{id}/risk
```

### Portfolios
```
GET  /portfolios
POST /portfolios
GET  /portfolios/{id}
POST /portfolios/{id}/positions
GET  /portfolios/{id}/snapshot
```

### Alerts & Webhooks
```
GET  /alerts/active
POST /alerts/{id}/resolve
POST /webhooks
GET  /webhooks
DEL  /webhooks/{id}
```

### Health & Metrics
```
GET /health    — postgres, redis, consumer lag
GET /metrics   — Prometheus exposition format
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- API keys for [Finnhub](https://finnhub.io) and/or [Alpha Vantage](https://www.alphavantage.co)

### Setup

**1. Clone the repository**
```bash
git clone https://github.com/manmathjukale/trading-signal-api.git
cd trading-signal-api
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and fill in your API keys and database credentials
```

**3. Start all services**
```bash
docker compose -f docker/docker-compose.yml --env-file .env up --build
```

**4. Run migrations**
```bash
docker exec -it trading-api alembic upgrade head
```

**5. Verify**
```bash
curl http://localhost:8000/health
```

Services available:
- API: `http://localhost:8000`
- Streamlit dashboard: `http://localhost:8501`
- Adminer (DB UI): `http://localhost:8080`
- Prometheus metrics: `http://localhost:8000/metrics`

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/trading
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Market data providers
FINNHUB_API_KEY=
ALPHA_VANTAGE_API_KEY=

# Signal weights (optional — defaults enforce sum=1.0 per strategy)
TF_WEIGHT_MACD=0.30
TF_WEIGHT_EMA=0.25
# ... see .env.example for full list
```

---

## Production Features

- **Idempotent consumers** — Redis SETNX deduplication prevents double-processing on consumer restart
- **Retry + DLQ** — Failed messages retried 3x with exponential backoff; unrecoverable messages routed to `price-events-dlq`
- **Graceful shutdown** — SIGTERM handler lets consumers finish the current message before exiting
- **Docker stop grace period** — 60s for consumers, 30s for API, preventing mid-flight kills
- **Prometheus metrics** — Ingestion latency histogram, Redis hit/miss counters, consumer lag gauge at `/metrics`
- **Webhook HMAC signing** — `X-Webhook-Signature: sha256=...` on every delivery
- **Partitioned PostgreSQL** — `price_points` partitioned by month for query performance at scale

---

## Dashboard Screenshots

> Screenshots stored in [`screenshots/`](screenshots/)

---

## Disclaimer

This system provides analytical signals and risk metrics for research and educational purposes. It does not constitute financial advice and does not guarantee trading outcomes.

---

## Author

**Manmath Jukale** — [GitHub](https://github.com/manmathjukale) · [LinkedIn](https://linkedin.com/in/jukalemanmath)
