from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.heatmap import router as heatmap_router
from app.api.v1.endpoints.mvg import router as mvg_router

router = APIRouter()
router.include_router(health_router, tags=["meta"])
router.include_router(mvg_router, prefix="/mvg", tags=["mvg"])
router.include_router(heatmap_router, prefix="/heatmap", tags=["heatmap"])
