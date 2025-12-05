"""
Transit API endpoints package.

Provides GTFS-based transit data endpoints for Germany-wide coverage.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.transit.departures import router as departures_router
from app.api.v1.endpoints.transit.stops import router as stops_router

router = APIRouter()
router.include_router(departures_router)
router.include_router(stops_router)
