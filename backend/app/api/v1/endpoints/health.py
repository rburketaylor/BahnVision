from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    """Lightweight readiness probe."""
    return {"status": "ok"}
