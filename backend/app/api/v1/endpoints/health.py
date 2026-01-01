import time

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()

# Track app startup time module-level
_APP_START_TIME = time.time()


@router.get("/health")
async def healthcheck() -> dict:
    """Lightweight readiness probe with uptime and version info."""
    settings = get_settings()
    uptime = time.time() - _APP_START_TIME
    return {
        "status": "ok",
        "version": settings.otel_service_version,
        "uptime_seconds": round(uptime, 1),
    }
