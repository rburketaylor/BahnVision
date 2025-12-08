"""Tests for OpenTelemetry configuration.

Target: app/core/telemetry.py (53 surviving mutations → improve to 60%+)
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from opentelemetry import trace


class TestConfigureOpentelemetry:
    """Tests for configure_opentelemetry function."""

    def test_disabled_logs_message_and_returns_early(self, caplog):
        """When disabled, should log and return without configuring."""
        from app.core.telemetry import configure_opentelemetry

        with caplog.at_level(logging.INFO):
            configure_opentelemetry(
                service_name="test-service",
                service_version="1.0.0",
                otlp_endpoint="http://localhost:4317",
                enabled=False,
            )

        assert "tracing is disabled" in caplog.text.lower()

    @patch("app.core.telemetry.set_global_textmap")
    @patch("app.core.telemetry.trace")
    @patch("app.core.telemetry.TracerProvider")
    @patch("app.core.telemetry.OTLPSpanExporter")
    @patch("app.core.telemetry.BatchSpanProcessor")
    def test_enabled_configures_tracer_provider(
        self,
        mock_batch_processor,
        mock_exporter,
        mock_tracer_provider,
        mock_trace,
        mock_set_textmap,
        caplog,
    ):
        """When enabled, should configure tracer provider correctly."""
        from app.core.telemetry import configure_opentelemetry

        mock_provider_instance = MagicMock()
        mock_tracer_provider.return_value = mock_provider_instance

        with caplog.at_level(logging.INFO):
            configure_opentelemetry(
                service_name="test-service",
                service_version="1.0.0",
                otlp_endpoint="http://localhost:4317",
                enabled=True,
            )

        # Verify B3 propagator was set
        mock_set_textmap.assert_called_once()

        # Verify tracer provider was configured
        mock_tracer_provider.assert_called_once()
        mock_trace.set_tracer_provider.assert_called_once_with(mock_provider_instance)

        # Verify OTLP exporter was created with correct endpoint
        mock_exporter.assert_called_once()
        call_kwargs = mock_exporter.call_args.kwargs
        assert call_kwargs["endpoint"] == "http://localhost:4317"

        # Verify batch processor was added
        mock_batch_processor.assert_called_once()
        mock_provider_instance.add_span_processor.assert_called_once()

        # Verify success message logged
        assert "test-service" in caplog.text

    @patch("app.core.telemetry.set_global_textmap")
    def test_enabled_handles_exception_gracefully(self, mock_set_textmap, caplog):
        """When configuration fails, should log warning and continue."""
        from app.core.telemetry import configure_opentelemetry

        mock_set_textmap.side_effect = RuntimeError("Configuration failed")

        with caplog.at_level(logging.WARNING):
            # Should not raise
            configure_opentelemetry(
                service_name="test-service",
                service_version="1.0.0",
                otlp_endpoint="http://localhost:4317",
                enabled=True,
            )

        assert "failed to configure" in caplog.text.lower()

    @patch("app.core.telemetry.set_global_textmap")
    @patch("app.core.telemetry.trace")
    @patch("app.core.telemetry.TracerProvider")
    @patch("app.core.telemetry.OTLPSpanExporter")
    @patch("app.core.telemetry.BatchSpanProcessor")
    def test_enabled_passes_headers_to_exporter(
        self,
        mock_batch_processor,
        mock_exporter,
        mock_tracer_provider,
        mock_trace,
        mock_set_textmap,
    ):
        """OTLP headers should be passed to exporter."""
        from app.core.telemetry import configure_opentelemetry

        configure_opentelemetry(
            service_name="test-service",
            service_version="1.0.0",
            otlp_endpoint="http://localhost:4317",
            otlp_headers="authorization=Bearer token123",
            enabled=True,
        )

        call_kwargs = mock_exporter.call_args.kwargs
        assert call_kwargs["headers"] == "authorization=Bearer token123"


class TestInstrumentFastapi:
    """Tests for instrument_fastapi function."""

    def test_disabled_does_nothing(self):
        """When disabled, should not instrument app."""
        from app.core.telemetry import instrument_fastapi

        mock_app = MagicMock()

        with patch("app.core.telemetry.FastAPIInstrumentor") as mock_instrumentor:
            instrument_fastapi(mock_app, enabled=False)
            mock_instrumentor.instrument_app.assert_not_called()

    @patch("app.core.telemetry.FastAPIInstrumentor")
    def test_enabled_instruments_app(self, mock_instrumentor, caplog):
        """When enabled, should instrument the FastAPI app."""
        from app.core.telemetry import instrument_fastapi

        mock_app = MagicMock()

        with caplog.at_level(logging.INFO):
            instrument_fastapi(mock_app, enabled=True)

        mock_instrumentor.instrument_app.assert_called_once_with(mock_app)
        assert "instrumentation enabled" in caplog.text.lower()

    @patch("app.core.telemetry.FastAPIInstrumentor")
    def test_enabled_handles_exception(self, mock_instrumentor, caplog):
        """When instrumentation fails, should log warning."""
        from app.core.telemetry import instrument_fastapi

        mock_instrumentor.instrument_app.side_effect = RuntimeError(
            "Instrumentation failed"
        )
        mock_app = MagicMock()

        with caplog.at_level(logging.WARNING):
            # Should not raise
            instrument_fastapi(mock_app, enabled=True)

        assert "failed to instrument" in caplog.text.lower()


class TestInstrumentHttpx:
    """Tests for instrument_httpx function."""

    def test_disabled_does_nothing(self):
        """When disabled, should not instrument httpx."""
        from app.core.telemetry import instrument_httpx

        with patch("app.core.telemetry.HTTPXClientInstrumentor") as mock_instrumentor:
            instrument_httpx(enabled=False)
            mock_instrumentor().instrument.assert_not_called()

    @patch("app.core.telemetry.HTTPXClientInstrumentor")
    def test_enabled_instruments_httpx(self, mock_instrumentor_class, caplog):
        """When enabled, should instrument httpx client."""
        from app.core.telemetry import instrument_httpx

        mock_instance = MagicMock()
        mock_instrumentor_class.return_value = mock_instance

        with caplog.at_level(logging.INFO):
            instrument_httpx(enabled=True)

        mock_instance.instrument.assert_called_once()
        assert "httpx" in caplog.text.lower()

    @patch("app.core.telemetry.HTTPXClientInstrumentor")
    def test_enabled_handles_exception(self, mock_instrumentor_class, caplog):
        """When instrumentation fails, should log warning."""
        from app.core.telemetry import instrument_httpx

        mock_instance = MagicMock()
        mock_instance.instrument.side_effect = RuntimeError("Instrumentation failed")
        mock_instrumentor_class.return_value = mock_instance

        with caplog.at_level(logging.WARNING):
            # Should not raise
            instrument_httpx(enabled=True)

        assert "failed to instrument" in caplog.text.lower()


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_returns_tracer_instance(self):
        """Should return a Tracer instance."""
        from app.core.telemetry import get_tracer

        tracer = get_tracer()
        assert isinstance(tracer, trace.Tracer)


class TestAddTraceparentHeader:
    """Tests for add_traceparent_header function."""

    def test_returns_copy_of_headers(self):
        """Should return a copy, not modify the original."""
        from app.core.telemetry import add_traceparent_header

        original = {"Content-Type": "application/json"}
        result = add_traceparent_header(original)

        # Should be a different dict
        assert result is not original
        # Original should be unchanged
        assert original == {"Content-Type": "application/json"}

    def test_preserves_existing_headers(self):
        """Should keep existing headers in the result."""
        from app.core.telemetry import add_traceparent_header

        original = {"Content-Type": "application/json", "Accept": "application/json"}
        result = add_traceparent_header(original)

        assert result["Content-Type"] == "application/json"
        assert result["Accept"] == "application/json"

    @patch("opentelemetry.propagate.inject")
    def test_calls_inject_on_headers_copy(self, mock_inject):
        """Should call inject() on the headers copy."""
        from app.core.telemetry import add_traceparent_header

        original = {"Content-Type": "application/json"}
        result = add_traceparent_header(original)

        mock_inject.assert_called_once()
        # The argument should be target dict (the copy)
        injected_dict = mock_inject.call_args[0][0]
        assert injected_dict == result
