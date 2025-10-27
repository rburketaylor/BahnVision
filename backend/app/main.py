from fastapi import FastAPI

from app.api.routes import api_router


def create_app() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title="BahnVision API",
        description="Backend service for BahnVision using FastAPI and MVG live data.",
        version="0.1.0",
    )

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
