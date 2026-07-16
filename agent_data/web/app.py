"""FastAPI application entry point."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent_data.web.auth import AuthManager
from agent_data.web.routes import router

logger = logging.getLogger(__name__)


def create_app(
    engine=None,
    data_sources: Optional[list] = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        engine: NL2SQLEngine instance.
        data_sources: List of data source configurations.

    Returns:
        FastAPI application instance.
    """
    app = FastAPI(
        title="智能问数 API",
        description="Natural language data query service powered by NL2SQL",
        version="0.1.0",
    )

    # Store engine in app state
    app.state.engine = engine
    app.state.data_sources = data_sources or []

    # Auth manager (SQLite-backed user + API key store)
    app.state.auth = AuthManager()

    # CORS configuration
    # TODO(prod): 收紧 CORSMiddleware.allow_origins 到具体域名；v1 仅 dev 用 "*"。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    # Serve static files (frontend)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the main HTML page."""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "智能问数 API is running. Visit /docs for API documentation."}

    # Startup event
    @app.on_event("startup")
    async def startup():
        logger.info("Starting NL2SQL API server...")

    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Shutting down NL2SQL API server...")
        if engine and hasattr(engine, "llm") and engine.llm is not None:
            await engine.llm.close()

    return app


# Default app instance for uvicorn
app = create_app()
