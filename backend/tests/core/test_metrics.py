"""Unit tests for metrics recording helpers."""

from prometheus_client import CollectorRegistry, Counter, Histogram
import pytest

import app.core.metrics as metrics


@pytest.fixture
def metric_registry(monkeypatch):
    """Provide a fresh registry and rebind module-level metrics."""
    registry = CollectorRegistry()

    monkeypatch.setattr(
        metrics,
        "CACHE_EVENTS",
        Counter(
            "bahnvision_cache_events_total",
            "Cache events",
            ["cache", "event"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics,
        "CACHE_REFRESH_LATENCY",
        Histogram(
            "bahnvision_cache_refresh_seconds",
            "Cache refresh latency",
            ["cache"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics,
        "MVG_REQUESTS",
        Counter(
            "bahnvision_mvg_requests_total",
            "MVG requests",
            ["endpoint", "result"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics,
        "MVG_REQUEST_LATENCY",
        Histogram(
            "bahnvision_mvg_request_seconds",
            "MVG request latency",
            ["endpoint"],
            registry=registry,
        ),
    )
    monkeypatch.setattr(
        metrics,
        "MVG_TRANSPORT_REQUESTS",
        Counter(
            "bahnvision_mvg_transport_requests_total",
            "MVG transport requests",
            ["endpoint", "transport_type", "result"],
            registry=registry,
        ),
    )

    return registry


def test_record_cache_event_increments_counter(metric_registry):
    metrics.record_cache_event("mvg_departures", "hit")
    metrics.record_cache_event("mvg_departures", "hit")

    value = metric_registry.get_sample_value(
        "bahnvision_cache_events_total",
        {"cache": "mvg_departures", "event": "hit"},
    )
    assert value == 2.0


def test_observe_cache_refresh_records_latency(metric_registry):
    metrics.observe_cache_refresh("mvg_departures", 0.25)
    metrics.observe_cache_refresh("mvg_departures", 0.75)

    count = metric_registry.get_sample_value(
        "bahnvision_cache_refresh_seconds_count",
        {"cache": "mvg_departures"},
    )
    total = metric_registry.get_sample_value(
        "bahnvision_cache_refresh_seconds_sum",
        {"cache": "mvg_departures"},
    )

    assert count == 2.0
    assert total == pytest.approx(1.0)


def test_observe_mvg_request_updates_counters(metric_registry):
    metrics.observe_mvg_request("station_lookup", "success", 0.5)
    metrics.observe_mvg_request("station_lookup", "error", 1.5)

    success_value = metric_registry.get_sample_value(
        "bahnvision_mvg_requests_total",
        {"endpoint": "station_lookup", "result": "success"},
    )
    error_value = metric_registry.get_sample_value(
        "bahnvision_mvg_requests_total",
        {"endpoint": "station_lookup", "result": "error"},
    )
    latency_sum = metric_registry.get_sample_value(
        "bahnvision_mvg_request_seconds_sum",
        {"endpoint": "station_lookup"},
    )
    latency_count = metric_registry.get_sample_value(
        "bahnvision_mvg_request_seconds_count",
        {"endpoint": "station_lookup"},
    )

    assert success_value == 1.0
    assert error_value == 1.0
    assert latency_count == 2.0
    assert latency_sum == pytest.approx(2.0)


def test_record_mvg_transport_request(metric_registry):
    metrics.record_mvg_transport_request("departures", "UBAHN", "success")
    metrics.record_mvg_transport_request("departures", "BUS", "error")
    metrics.record_mvg_transport_request("departures", "UBAHN", "success")

    success_value = metric_registry.get_sample_value(
        "bahnvision_mvg_transport_requests_total",
        {"endpoint": "departures", "transport_type": "UBAHN", "result": "success"},
    )
    bus_error_value = metric_registry.get_sample_value(
        "bahnvision_mvg_transport_requests_total",
        {"endpoint": "departures", "transport_type": "BUS", "result": "error"},
    )

    assert success_value == 2.0
    assert bus_error_value == 1.0
