from prometheus_client import Counter, Gauge, Histogram

# ------------------------------------------------------------------
# Ingestion latency — how long a Tier 3 (external API) fetch takes
# ------------------------------------------------------------------
INGESTION_LATENCY = Histogram(
    "price_ingestion_latency_seconds",
    "Time spent fetching price from external provider (Tier 3 only)",
    ["provider", "symbol"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ------------------------------------------------------------------
# Redis cache — hit/miss counters, hit rate derived from these
# ------------------------------------------------------------------
CACHE_HITS = Counter(
    "price_cache_hits_total",
    "Number of price requests served from Redis cache",
    ["symbol"],
)

CACHE_MISSES = Counter(
    "price_cache_misses_total",
    "Number of price requests not found in Redis cache",
    ["symbol"],
)

# ------------------------------------------------------------------
# Consumer lag — how many messages behind each consumer group is
# ------------------------------------------------------------------
CONSUMER_LAG = Gauge(
    "kafka_consumer_lag_messages",
    "Number of messages the consumer group is behind the latest offset",
    ["consumer_group", "topic"],
)
