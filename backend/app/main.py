from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.metrics import router as metrics_router
from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    settings = get_settings()
    app = FastAPI(
        title="BahnVision API",
        description="Backend service for BahnVision using FastAPI and MVG live data.",
        version="0.1.0",
        lifespan=lifespan,
    )

    allow_origins = settings.cors_allow_origins
    allow_origin_regex = settings.cors_allow_origin_regex
    if allow_origins or allow_origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
            allow_credentials=bool(allow_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(metrics_router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
