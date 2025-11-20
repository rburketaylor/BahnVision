from contextlib import asynccontextmanager
import logging

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.telemetry import (
    configure_opentelemetry,
    instrument_fastapi,
    instrument_httpx,
)

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-Id"


def _configure_sqlalchemy_logging(database_echo: bool) -> None:
    """
    Silence verbose SQLAlchemy logs unless echo is explicitly enabled.

    SQLAlchemy logs under several namespaces (engine + pool). We drop them to
    WARNING by default so bulk INSERT statements and parameter dumps only show
    up when DATABASE_ECHO=true.
    """
    level = logging.INFO if database_echo else logging.WARNING
    for name in (
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.pool.impl.AsyncAdaptedQueuePool",
    ):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = database_echo


def _install_request_id_middleware(app: FastAPI) -> None:
    """Ensure each response includes a stable X-Request-Id header."""

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid4()))
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    settings = get_settings()

    # Configure OpenTelemetry at startup
    configure_opentelemetry(
        service_name=settings.otel_service_name,
        service_version=settings.otel_service_version,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        otlp_headers=settings.otel_exporter_otlp_headers,
        enabled=settings.otel_enabled,
    )

    # Instrument httpx for outbound request tracing
    instrument_httpx(enabled=settings.otel_enabled)

    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    settings = get_settings()
    app = FastAPI(
        title="BahnVision API",
        description="Backend service for BahnVision using FastAPI and MVG live data.",
        version="0.1.0",
        lifespan=lifespan,
    )

    _configure_sqlalchemy_logging(settings.database_echo)

    # Instrument FastAPI for tracing if enabled
    instrument_fastapi(app, enabled=settings.otel_enabled)
    _install_request_id_middleware(app)

    allow_origins = settings.cors_allow_origins
    allow_origin_regex = settings.cors_allow_origin_regex
    if allow_origins or allow_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=bool(allow_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(metrics_router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
