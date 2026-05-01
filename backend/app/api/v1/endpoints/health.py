import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.services.cache import CacheService, get_cache_service

router = APIRouter()

# Track app startup time module-level
_APP_START_TIME = time.time()


@router.get("/health")
async def healthcheck() -> dict:
    """Lightweight liveness probe with uptime and version info."""
    settings = get_settings()
    uptime = time.time() - _APP_START_TIME
    return {
        "status": "ok",
        "version": settings.otel_service_version,
        "uptime_seconds": round(uptime, 1),
    }


async def _check_cache_ready(cache: CacheService) -> None:
    """Verify cache dependency is reachable."""
    client = getattr(cache, "_client", None)
    if client is not None and hasattr(client, "ping"):
        await client.ping()
        return

    if hasattr(cache, "get_json"):
        await cache.get_json("__healthcheck__:ready")
        return

    if hasattr(cache, "get"):
        await cache.get("__healthcheck__:ready")
        return

    raise RuntimeError("cache service does not expose readiness check operation")


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
):
    """Dependency readiness probe for DB and cache."""
    checks = {"database": "ok", "cache": "ok"}
    errors: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        checks["database"] = "error"
        errors["database"] = str(exc)

    try:
        await _check_cache_ready(cache)
    except Exception as exc:
        checks["cache"] = "error"
        errors["cache"] = str(exc)

    if errors:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": checks,
                "errors": errors,
            },
        )

    return {
        "status": "ready",
        "checks": checks,
        "errors": {},
    }
