from contextlib import asynccontextmanager
import logging
import sys
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.metrics import router as metrics_router
from app.api.routes import api_router
from app.api.v1.shared.rate_limit import limiter
from app.core.config import get_settings
from app.core.database import engine
from app.core.telemetry import (
    configure_opentelemetry,
    instrument_fastapi,
    instrument_httpx,
)
from app.jobs.rt_processor import gtfs_rt_lifespan_manager
from app.jobs.gtfs_scheduler import GTFSFeedScheduler
from app.services.cache import get_cache_service
from app.services.gtfs_import_lock import init_import_lock
from app.services.gtfs_realtime_harvester import GTFSRTDataHarvester

# Configure logging for the application (after imports per PEP 8)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
# Ensure app modules log at INFO level
logging.getLogger("app").setLevel(logging.INFO)

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

    # Initialize cache service for GTFS-RT processor
    cache_service = get_cache_service()
    heatmap_cache_warmer = None

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

    # Initialize the GTFS import lock for coordination between
    # the GTFS feed importer and the realtime harvester
    init_import_lock(cache_service=cache_service)

    # Start GTFS static feed scheduler (handles initial import if DB empty)
    gtfs_scheduler = GTFSFeedScheduler(settings)
    await gtfs_scheduler.start()

    # Start GTFS-RT data harvester for historical persistence
    harvester: GTFSRTDataHarvester | None = None
    if settings.gtfs_rt_harvesting_enabled:
        harvester = GTFSRTDataHarvester(cache_service=cache_service)
        await harvester.start()
        logger.info("GTFS-RT data harvester started")

    # Warm common heatmap variants at startup to reduce first-page latency.
    try:
        from app.jobs.heatmap_cache_warmup import HeatmapCacheWarmer

        heatmap_cache_warmer = HeatmapCacheWarmer(cache_service)
        heatmap_cache_warmer.trigger(reason="startup")
    except Exception:
        logger.exception("Failed to trigger heatmap cache warmup at startup")

    # Start GTFS-RT background processor
    async with gtfs_rt_lifespan_manager(cache_service) as rt_processor:
        yield {"rt_processor": rt_processor, "harvester": harvester}

    # Stop harvester before shutdown
    if harvester:
        await harvester.stop()

    if heatmap_cache_warmer is not None:
        try:
            await heatmap_cache_warmer.shutdown()
        except Exception:
            logger.exception("Failed to stop heatmap cache warmer on shutdown")

    await gtfs_scheduler.stop()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    settings = get_settings()
    app = FastAPI(
        title="BahnVision",
        description="Backend service for BahnVision using FastAPI and GTFS transit data.",
        version="1.0.0",
        lifespan=lifespan,
    )

    _configure_sqlalchemy_logging(settings.database_echo)

    # Configure rate limiting using the shared limiter
    if settings.rate_limit_enabled:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
        logger.info("Rate limiting enabled")

    # Instrument FastAPI for tracing if enabled
    instrument_fastapi(app, enabled=settings.otel_enabled)
    _install_request_id_middleware(app)

    # Compress larger JSON responses (e.g., heatmap payloads)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    allow_origins = settings.cors_allow_origins
    allow_origin_regex = settings.cors_allow_origin_regex

    # In strict mode, only allow explicitly configured origins
    if settings.cors_strict_mode:
        # Validate origins are not overly permissive in production
        for origin in allow_origins:
            if "*" in origin and not origin.startswith("http://localhost"):
                raise ValueError(
                    f"Wildcard CORS origin '{origin}' not allowed in strict mode. "
                    "Use specific domains in production."
                )

    if allow_origins or allow_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=bool(allow_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "accept",
                "accept-language",
                "content-language",
                "content-type",
                "authorization",
                "x-request-id",
                "x-api-key",
            ],
        )

    app.include_router(metrics_router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
