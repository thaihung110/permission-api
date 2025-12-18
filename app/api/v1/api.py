"""
API Router - Combines all v1 endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, permissions

api_router = APIRouter()

# Include health endpoint without prefix (at root level)
api_router.include_router(health.router, tags=["Health"])

# Include permission endpoints with /permissions prefix
api_router.include_router(
    permissions.router, prefix="/permissions", tags=["Permissions"]
)
