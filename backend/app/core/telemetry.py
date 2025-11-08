"""OpenTelemetry configuration and initialization."""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def configure_opentelemetry(
    service_name: str,
    service_version: str,
    otlp_endpoint: str,
    otlp_headers: str | None = None,
    enabled: bool = False,
) -> None:
    """Configure OpenTelemetry tracing for the application.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OTLP collector endpoint
        otlp_headers: Optional OTLP headers
        enabled: Whether tracing is enabled
    """
    if not enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return

    try:
        # Configure propagators (B3 for compatibility with other services)
        set_global_textmap(B3MultiFormat())

        # Create resource with service metadata
        resource = Resource.create({
            "service.name": service_name,
            "service.version": service_version,
            "service.namespace": "bahnvision",
        })

        # Configure tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            headers=otlp_headers,
        )

        # Add batch span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        logger.info(f"OpenTelemetry configured for service '{service_name}'")
        logger.info(f"OTLP endpoint: {otlp_endpoint}")

    except Exception as e:
        logger.warning(f"Failed to configure OpenTelemetry: {e}")
        logger.info("Application will continue without tracing")


def instrument_fastapi(app: Any, enabled: bool = False) -> None:
    """Instrument FastAPI application for tracing.

    Args:
        app: FastAPI application instance
        enabled: Whether tracing is enabled
    """
    if not enabled:
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")


def instrument_httpx(enabled: bool = False) -> None:
    """Instrument httpx client for tracing.

    Args:
        enabled: Whether tracing is enabled
    """
    if not enabled:
        return

    try:
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX client instrumentation enabled")
    except Exception as e:
        logger.warning(f"Failed to instrument HTTPX: {e}")


def get_tracer() -> trace.Tracer:
    """Get the configured tracer instance."""
    return trace.get_tracer(__name__)


def add_traceparent_header(headers: dict[str, str]) -> dict[str, str]:
    """Add traceparent header to HTTP request headers if tracing is enabled.

    This allows propagating trace context to external services like MVG API.

    Args:
        headers: Existing HTTP headers

    Returns:
        Headers with traceparent added if available
    """
    from opentelemetry.propagate import inject

    headers_copy = headers.copy()
    inject(headers_copy)
    return headers_copy
