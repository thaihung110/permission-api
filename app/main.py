"""
Permission Management API - Main application entry point

This service manages permissions for Lakekeeper resources using OpenFGA.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.external.openfga_client import OpenFGAManager
from app.external.openfga_setup import OpenFGASetup

# Configure logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Global managers
openfga_manager: OpenFGAManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    global openfga_manager

    # Startup
    logger.info("Starting Permission Management API...")
    try:
        # Step 1: Validate OpenFGA (store and model must already exist)
        logger.info("Validating OpenFGA store and authorization model...")
        setup = OpenFGASetup(api_url=settings.openfga_api_url)

        # Validate store and model exist (will fail if they don't)
        # If OPENFGA_STORE_ID is set, validate that specific store
        # Otherwise, will use the first available store
        store_id = await setup.validate_store_and_model(
            store_id=settings.openfga_store_id
        )

        # Update settings with validated store_id
        if not settings.openfga_store_id:
            settings.openfga_store_id = store_id
            logger.info(f"Using OpenFGA store: {store_id}")

        # Step 2: Initialize OpenFGA client for regular operations
        openfga_manager = OpenFGAManager(
            api_url=settings.openfga_api_url,
            store_id=settings.openfga_store_id,
        )

        await openfga_manager.initialize()
        logger.info("OpenFGA manager initialized successfully")

        # Make managers available to routers
        app.state.openfga = openfga_manager

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Permission Management API...")
    if openfga_manager:
        await openfga_manager.close()


app = FastAPI(
    title=settings.project_name,
    description="Authorization service for Lakekeeper resources using OpenFGA",
    version=settings.version,
    lifespan=lifespan,
)

@app.middleware("http")
async def log_raw_body(request: Request, call_next):
    """Log raw request body for every incoming API request."""
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()
        try:
            raw_str = body.decode("utf-8", errors="replace")
            logger.info(
                "[REQUEST] %s %s | raw_body=%s",
                request.method,
                request.url.path,
                raw_str if raw_str else "(empty)",
            )
        except Exception as e:
            logger.warning("[REQUEST] Failed to log body: %s", e)

        # Make body consumable again for route handlers
        async def receive():
            return {"type": "http.request", "body": body}

        request = Request(request.scope, receive)
    else:
        logger.info("[REQUEST] %s %s | (no body)", request.method, request.url.path)
    response = await call_next(request)
    return response


# Include API router with v1 prefix
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": settings.project_name,
        "version": settings.version,
        "status": "running",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "app.main:app", host=host, port=port, reload=False, log_level="info"
    )
