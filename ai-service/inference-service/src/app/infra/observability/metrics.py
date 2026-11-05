"""Prometheus metrics for inference-service (prometheus-client, default registry).

Why prometheus-client rather than a hand-rolled collector: it's thread-safe, produces the
exposition format Prometheus scrapes, and gives histograms (p50/p95/p99) instead of a mean —
a mean latency hides exactly the tail that hurts users. Counters are cumulative; Prometheus
derives rates (`rate()`), error ratios and hit ratios at query time, so we store raw counts,
never precomputed rates.

Keep label values low-cardinality (route *templates*, enums, model names) — never user input.
The service runs a single uvicorn worker, so the default (non-multiprocess) registry is correct;
revisit if `--workers` is ever raised.
"""
from prometheus_client import Counter, Gauge, Histogram

_HTTP_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_LLM_BUCKETS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0)
_FAST_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)

# ── HTTP (ObservabilityMiddleware) ───────────────────────────────────────────
HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled.", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
    buckets=_HTTP_BUCKETS,
)
HTTP_IN_PROGRESS = Gauge("http_requests_in_progress", "HTTP requests currently being handled.")

# ── Search pipeline stages ───────────────────────────────────────────────────
EMBEDDING_LATENCY = Histogram(
    "embedding_duration_seconds", "Time to embed one query.", buckets=_FAST_BUCKETS
)
VECTOR_SEARCH_LATENCY = Histogram(
    "vector_search_duration_seconds",
    "Time spent in the pgvector similarity search.",
    buckets=_FAST_BUCKETS,
)
SEARCH_RESULTS = Histogram(
    "trial_search_results",
    "Number of trial cards returned per search (the 0 bucket = empty searches).",
    buckets=(0, 1, 5, 10, 20, 50),
)

# ── Query planner ────────────────────────────────────────────────────────────
PLANNER_CACHE = Counter(
    "query_planner_cache_total", "Plan cache lookups.", ["result"]  # hit | miss
)
PLANNER_ROUTE = Counter(
    "query_planner_route_total",
    "Which planner a query was routed to.",
    ["planner"],  # llm | rule_based (fast path: no filter signal, LLM skipped)
)
LLM_FALLBACKS = Counter(
    "llm_planner_fallbacks_total", "LLM planner errors that fell back to the rule-based planner."
)

# ── LLM (OpenAI) ─────────────────────────────────────────────────────────────
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM planner calls.",
    ["model", "outcome"],  # ok | refusal | error
)
LLM_LATENCY = Histogram(
    "llm_request_duration_seconds", "LLM call latency.", ["model"], buckets=_LLM_BUCKETS
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM tokens consumed (multiply by your model's price to track spend).",
    ["model", "direction"],  # input | output
)
