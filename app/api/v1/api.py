"""
API Router - Combines all v1 endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, permissions, row_filter

api_router = APIRouter()

# Include health endpoint without prefix (at root level)
api_router.include_router(health.router, tags=["Health"])

# Include permission endpoints with /permissions prefix
api_router.include_router(
    permissions.router, prefix="/permissions", tags=["Permissions"]
)

# Include row filter endpoints with /permissions prefix
api_router.include_router(
    row_filter.router, prefix="/permissions", tags=["Row Filters"]
)
