"""
Route planning placeholder endpoint.

This mirrors the legacy MVG /routes/plan route but explicitly returns
501 until GTFS-based journey planning is implemented.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/routes/plan")
async def plan_route_placeholder():
    """Return a clear 501 response for unimplemented route planning."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Route planning is not yet available. This endpoint will be "
            "implemented when GTFS-based journey planning ships (Phase 5)."
        ),
    )
