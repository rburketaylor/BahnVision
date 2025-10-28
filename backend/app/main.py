from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.metrics import router as metrics_router
from app.api.routes import api_router
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title="BahnVision API",
        description="Backend service for BahnVision using FastAPI and MVG live data.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(metrics_router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
