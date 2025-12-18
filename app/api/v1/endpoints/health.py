"""
Health check endpoint
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.external.openfga_client import OpenFGAManager
from app.schemas.health import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint"""
    try:
        openfga = request.app.state.openfga
        openfga_healthy = await openfga.health_check()

        if not openfga_healthy:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "openfga_connected": openfga_healthy,
                },
            )

        return HealthResponse(
            status="healthy",
            openfga_connected=True,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "openfga_connected": False,
                "error": str(e),
            },
        )
