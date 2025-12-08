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
TRANSIT_REQUESTS = Counter(
    "bahnvision_transit_requests_total",
    "Outbound Transit client requests.",
    labelnames=("endpoint", "result"),
)
TRANSIT_REQUEST_LATENCY = Histogram(
    "bahnvision_transit_request_seconds",
    "Latency of outbound Transit client requests.",
    labelnames=("endpoint",),
)
TRANSIT_TRANSPORT_REQUESTS = Counter(
    "bahnvision_transit_transport_requests_total",
    "Outbound Transit client requests per transport type.",
    labelnames=("endpoint", "transport_type", "result"),
)


def record_cache_event(cache: str, event: str) -> None:
    """Increment a cache event counter."""
    CACHE_EVENTS.labels(cache=cache, event=event).inc()


def observe_cache_refresh(cache: str, duration_seconds: float) -> None:
    """Record cache refresh latency."""
    CACHE_REFRESH_LATENCY.labels(cache=cache).observe(duration_seconds)


def observe_transit_request(
    endpoint: str, result: str, duration_seconds: float
) -> None:
    """Record Transit request result and latency."""
    TRANSIT_REQUESTS.labels(endpoint=endpoint, result=result).inc()
    TRANSIT_REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration_seconds)


def record_transit_transport_request(
    endpoint: str, transport_type: str, result: str
) -> None:
    """Record Transit request result per transport type."""
    TRANSIT_TRANSPORT_REQUESTS.labels(
        endpoint=endpoint, transport_type=transport_type, result=result
    ).inc()
