from __future__ import annotations

from prometheus_client import Counter, Histogram

CACHE_EVENTS = Counter(
    "bahnvision_cache_events_total",
    "Cache operations recorded by BahnVision.",
    labelnames=("cache", "event"),
)
CACHE_REFRESH_LATENCY = Histogram(
    "bahnvision_cache_refresh_seconds",
    "Latency of cache refresh operations.",
    labelnames=("cache",),
)
MVG_REQUESTS = Counter(
    "bahnvision_mvg_requests_total",
    "Outbound MVG client requests.",
    labelnames=("endpoint", "result"),
)
MVG_REQUEST_LATENCY = Histogram(
    "bahnvision_mvg_request_seconds",
    "Latency of outbound MVG client requests.",
    labelnames=("endpoint",),
)
MVG_TRANSPORT_REQUESTS = Counter(
    "bahnvision_mvg_transport_requests_total",
    "Outbound MVG client requests per transport type.",
    labelnames=("endpoint", "transport_type", "result"),
)


def record_cache_event(cache: str, event: str) -> None:
    """Increment a cache event counter."""
    CACHE_EVENTS.labels(cache=cache, event=event).inc()


def observe_cache_refresh(cache: str, duration_seconds: float) -> None:
    """Record cache refresh latency."""
    CACHE_REFRESH_LATENCY.labels(cache=cache).observe(duration_seconds)


def observe_mvg_request(endpoint: str, result: str, duration_seconds: float) -> None:
    """Record MVG request result and latency."""
    MVG_REQUESTS.labels(endpoint=endpoint, result=result).inc()
    MVG_REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration_seconds)


def record_mvg_transport_request(
    endpoint: str, transport_type: str, result: str
) -> None:
    """Record MVG request result per transport type."""
    MVG_TRANSPORT_REQUESTS.labels(
        endpoint=endpoint, transport_type=transport_type, result=result
    ).inc()
