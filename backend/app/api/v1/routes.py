from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.heatmap import router as heatmap_router
from app.api.v1.endpoints.ingestion import router as ingestion_router
from app.api.v1.endpoints.transit import router as transit_router

router = APIRouter()
router.include_router(health_router, tags=["meta"])
router.include_router(transit_router, prefix="/transit", tags=["transit"])
router.include_router(heatmap_router, prefix="/heatmap", tags=["heatmap"])
router.include_router(ingestion_router, prefix="/system", tags=["system"])
