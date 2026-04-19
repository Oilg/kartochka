from prometheus_client import Counter, Gauge, Histogram

generations_total = Counter(
    "kartochka_generations_total",
    "Total number of image generations",
    ["status", "output_format", "plan"],
)

generation_duration_seconds = Histogram(
    "kartochka_generation_duration_seconds",
    "Time spent generating images in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

http_requests_total = Counter(
    "kartochka_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

registered_users_total = Gauge(
    "kartochka_registered_users_total",
    "Total number of registered users",
)

active_users_30d = Gauge(
    "kartochka_active_users_30d",
    "Monthly Active Users — users with at least one request in the last 30 days",
)
