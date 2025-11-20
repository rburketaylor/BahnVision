"""
MVG endpoints package.

This package provides all MVG-related endpoints with modular organization:
- departures.py: /departures endpoint
- stations.py: /stations/search and /stations/list endpoints
- routes.py: /routes/plan endpoint

The package maintains the same interface as the original single router
while providing better organization and maintainability.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.mvg.departures import router as departures_router
from app.api.v1.endpoints.mvg.routes import router as routes_router
from app.api.v1.endpoints.mvg.stations import router as stations_router

# Create the main MVG router
router = APIRouter()

# Include all endpoint routers with proper organization
router.include_router(departures_router, tags=["departures"])
router.include_router(stations_router, tags=["stations"])
router.include_router(routes_router, tags=["routes"])

# Export the router for import in the main routes module
__all__ = ["router"]
