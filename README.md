# 📈 Systematic Trading Signal & Risk API

> **A real-time backend platform for systematic signal generation, portfolio risk monitoring, and anomaly alerting.**

---

## 🚀 Overview

**Systematic Trading Signal & Risk API** is a backend-first platform that ingests live financial market data, processes it through an event-driven pipeline, computes trading signals and portfolio risk metrics, and delivers real-time alerts via APIs and webhooks.

This system is designed as **middleware between market data providers and trading strategies**, enabling developers and traders to integrate signal generation and risk monitoring into their applications without building the infrastructure from scratch.

---

## 🎯 Problem

Retail algorithmic traders and small prop desks face a fundamental challenge:

* Market data APIs provide **raw price feeds**, not actionable insights
* Risk monitoring systems are either **expensive or internal-only**
* Building signal + risk infrastructure requires **months of engineering effort**
* Most tools are **fragmented** (data, charts, execution — but no unified backend layer)

As a result:

* Traders operate without real-time risk visibility
* Strategies lack systematic signal generation
* Systems cannot react to anomalies or volatility spikes in time

---

## 💡 Solution

This project provides a **plug-and-play backend service** that:

* Ingests real-time market data (stocks + crypto)
* Generates composite trading signals using technical indicators
* Computes portfolio-level risk metrics continuously
* Detects anomalies and volatility spikes
* Pushes alerts via webhooks
* Exposes all functionality via REST and WebSocket APIs

---

## 🧠 Key Capabilities

### 📊 Real-Time Data Pipeline

* Multi-provider ingestion (Finnhub, Binance US)
* Event streaming via Kafka
* Partitioned PostgreSQL storage (time-based)
* Redis caching for low-latency reads
* WebSocket streaming for live updates

---

### ⚡ Signal Engine

Generates **BUY / SELL / HOLD signals** using a composite indicator model:

* Trend: EMA / SMA
* Momentum: MACD, RSI
* Volatility: Bollinger Bands
* Trend strength: ADX
* Volume confirmation: OBV

Each signal includes:

* Confidence score
* Indicator breakdown
* Timestamped audit record

> Signals are computed using **multiple complementary indicators**, since individual indicators are not reliable in isolation.

---

### 📉 Risk Engine

Continuously evaluates portfolio-level risk:

* Portfolio value & P&L
* Parametric VaR (95%)
* Sharpe ratio
* Maximum drawdown
* Rolling volatility
* Correlation matrix

Supports **threshold-based alerts**:

* VaR exceeding limits
* Drawdown breaches
* Concentration risk
* Volatility spikes

---

### 🚨 Anomaly Detection

Detects unusual market behavior:

* Z-score outliers (3σ / 4σ)
* Moving average divergence
* Bollinger band breakouts
* Volume anomalies

Triggers:

* Real-time alerts
* Webhook notifications
* Persistent anomaly logs

---

### 🔔 Alerting System

* Webhook-based event delivery
* Push-based architecture (no polling required)
* Supports:

  * signal triggers
  * anomaly alerts
  * risk threshold breaches

---

## 🏗️ Architecture

```
Market Data Providers (Finnhub, Binance US)
   ↓
Ingestion Layer (FastAPI + Async Polling Workers)
   ↓
Kafka (price-events topic)
   ↓
Kafka Consumers
   ├── Moving Average Service  →  PostgreSQL
   └── Anomaly Detector        →  PostgreSQL + Webhook Dispatcher → Registered Webhooks

PostgreSQL (Partitioned Storage)
   ↑── Signal Engine   (on-demand per API request, persists to signal_history)
   ↑── Risk Engine     (on-demand per API request)

Redis (Caching Layer)

REST + WebSocket + Webhook APIs
```

---

## ⚙️ Tech Stack

### Backend

* FastAPI (async)
* SQLAlchemy (async ORM)
* Kafka (confluent_kafka / aiokafka)
* PostgreSQL (partitioned tables)
* Redis

### Infra

* Docker (multi-container setup)
* Kafka + Zookeeper
* Adminer (DB UI)

### Data Processing

* NumPy / SciPy (risk calculations)
* Async background workers

---

## 📡 APIs

### Market Data

* `GET /prices/latest`
* `GET /prices/history`
* `WS /prices/stream`

### Signals

* `GET /signals/{symbol}`
* `GET /signals/history`

### Risk

* `GET /portfolio/{id}/risk`
* `GET /portfolio/{id}/metrics`

### Alerts & Webhooks

* `GET /alerts`
* `POST /alerts/{id}/acknowledge`
* `POST /webhooks`
* `GET /webhooks`
* `DELETE /webhooks/{id}`

### Admin / Health

* `GET /health`
* `GET /admin/workers`
* `GET /admin/providers`

---

## 🧩 Indicator Framework

Indicators are grouped by function:

**MVP (Phase 2)**

| Category       | Indicators              |
| -------------- | ----------------------- |
| Trend          | SMA, EMA, MACD          |
| Momentum       | RSI                     |
| Volatility     | Bollinger Bands         |
| Volume         | OBV                     |
| Trend Strength | ADX                     |

**V2 (after core is stable)**

| Category       | Indicators                          |
| -------------- | ----------------------------------- |
| Momentum       | Stochastic Oscillator               |
| Volume         | Accumulation/Distribution Line      |
| Trend          | Aroon                               |
| Structure      | Fibonacci Retracement, Ichimoku     |

> The system combines indicators instead of relying on a single signal, improving robustness.

---

## 📊 Signal Generation Model

Signals are computed using a **composite scoring system**:

Example:

* EMA trend → bullish signal
* MACD crossover → momentum signal
* RSI oversold → reversal signal
* OBV divergence → confidence adjustment
* ADX → trend strength weighting

### Output

```json
{
  "symbol": "AAPL",
  "signal": "BUY",
  "confidence": 78,
  "strategy_mode": "trend-following",
  "indicators": {
    "ema": "bullish",
    "macd": "bullish crossover",
    "rsi": "oversold recovery",
    "adx": "strong trend",
    "obv": "confirming"
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

---

## 📉 Risk Metrics

| Metric       | Description                   |
| ------------ | ----------------------------- |
| VaR (95%)    | Expected worst-case loss      |
| Sharpe Ratio | Risk-adjusted return          |
| Max Drawdown | Largest peak-to-trough loss   |
| Volatility   | Standard deviation of returns |
| Correlation  | Asset interdependence         |

---

## 🖥️ Minimal Operator UI (Streamlit)

### 1. Signal Monitor

* Symbol → Signal → Confidence → Indicator breakdown

### 2. Portfolio Risk Dashboard

* VaR gauge
* Sharpe ratio
* Drawdown visualization
* Correlation heatmap

### 3. Anomaly Feed

* Real-time alerts
* Severity levels
* Acknowledge / resolve actions

---

## 🔥 Production Features

* Idempotent Kafka consumers
* Retry + dead-letter queue (DLQ)
* Structured logging
* Redis cache strategy (TTL + invalidation)
* Graceful shutdown
* Health checks
* Load-tested pipeline

---

## 🛠️ Build Plan

### Phase 1

* Data ingestion + Kafka + storage

### Phase 2

* Signal engine (EMA, MACD, RSI, Bollinger, ADX, OBV)

### Phase 3

* Portfolio risk engine

### Phase 4

* Anomaly detection + alerting

### Phase 5

* Operator dashboard (Streamlit)

### Phase 6

* Production hardening (metrics, retries, scaling)

---

## 🎯 Use Cases

* Algorithmic trading systems
* Portfolio monitoring tools
* Fintech backend infrastructure
* Risk monitoring services
* Trading bots

---

## 📌 Positioning

### One-line

**Backend infrastructure for real-time trading signals and portfolio risk monitoring**

### Analogy

> What Alpaca provides for execution, this system provides for **signals + risk intelligence**

---

## ⚠️ Disclaimer

This system provides analytical signals and risk metrics.
It does not guarantee trading outcomes and should not be used as financial advice.

---

## 👨‍💻 Author

**Manmath Jukale**