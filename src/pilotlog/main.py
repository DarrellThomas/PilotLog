"""Main entry point for PilotLog application."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from pilotlog.config import settings
from pilotlog.database import init_db
from pilotlog.api import router

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure application logging."""
    settings.ensure_directories()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.log_path / "pilotlog.log"),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    setup_logging()
    logger.info("Starting PilotLog application")
    settings.ensure_directories()
    await init_db()
    logger.info(f"Database initialized at {settings.db_path}")
    yield
    logger.info("Shutting down PilotLog application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="PilotLog",
        description="A local-first pilot logbook for flight record visualization and analysis",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(router, prefix="/api")

    # Serve static frontend files if they exist
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

    return app


app = create_app()


def main() -> None:
    """Run the application server."""
    uvicorn.run(
        "pilotlog.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
